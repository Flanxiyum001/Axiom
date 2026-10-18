"""The explicit smoke command is exercised with a fake provider only."""

import json

import httpx
import pytest
from openai import AuthenticationError, RateLimitError

from backend.llm.base import ProviderError
from backend.llm.nebius import NebiusLLMProvider
from scripts import smoke_nebius_reasoning as smoke


def test_smoke_requires_credentials_without_network(monkeypatch, capsys):
    monkeypatch.setattr(smoke, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    assert smoke.main(["--live"]) == 1
    assert "NEBIUS_API_KEY is missing" in capsys.readouterr().err


def test_smoke_uses_configured_model_once(monkeypatch, capsys):
    monkeypatch.setattr(smoke, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("NEBIUS_API_KEY", "private-test-key")
    monkeypatch.setenv("NEBIUS_BASE_URL", smoke.BASE_URL)
    monkeypatch.setenv("NEBIUS_MODEL", smoke.MODEL)
    calls = []

    class FakeProvider:
        name = "nebius"

        def __init__(self, **kwargs):
            assert kwargs["model"] == smoke.MODEL
            assert kwargs["base_url"] == smoke.BASE_URL
            assert kwargs["max_retries"] == 0
            self.last_response_model = smoke.MODEL

        def generate(self, **kwargs):
            calls.append(kwargs)
            return smoke.SmokeReply(message=smoke.MARKER)

    monkeypatch.setattr(smoke, "NebiusLLMProvider", FakeProvider)
    assert smoke.main(["--live"]) == 0
    assert len(calls) == 1
    assert calls[0]["output_type"] is smoke.SmokeReply
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "provider": "nebius",
        "requested_model": smoke.MODEL,
        "response_model": smoke.MODEL,
        "validated": True,
    }
    assert "private-test-key" not in output


def test_smoke_rejects_wrong_response_model(monkeypatch, capsys):
    monkeypatch.setattr(smoke, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("NEBIUS_API_KEY", "private-test-key")
    monkeypatch.setenv("NEBIUS_BASE_URL", smoke.BASE_URL)
    monkeypatch.setenv("NEBIUS_MODEL", smoke.MODEL)

    class FakeProvider:
        name = "nebius"
        last_response_model = "other-model"

        def __init__(self, **kwargs):
            pass

        def generate(self, **kwargs):
            return smoke.SmokeReply(message=smoke.MARKER)

    monkeypatch.setattr(smoke, "NebiusLLMProvider", FakeProvider)
    assert smoke.main(["--live"]) == 1
    captured = capsys.readouterr()
    assert "did not identify" in captured.err
    assert "private-test-key" not in captured.err + captured.out


def test_provider_does_not_expose_server_error_or_model_body(monkeypatch, caplog):
    secret = "private-test-key"

    class AuthClient:
        def create(self, **kwargs):
            request = httpx.Request("POST", smoke.BASE_URL + "chat/completions")
            response = httpx.Response(401, request=request)
            raise AuthenticationError(
                f"Authorization: Bearer {secret}", response=response, body=None
            )

    client = type(
        "Client",
        (),
        {
            "chat": type(
                "Chat",
                (),
                {
                    "completions": AuthClient(),
                },
            )()
        },
    )()
    monkeypatch.setattr("backend.llm.nebius.OpenAI", lambda **kwargs: client)
    provider = NebiusLLMProvider(api_key=secret, model=smoke.MODEL, max_retries=0)
    with pytest.raises(ProviderError, match="authentication failed") as exc:
        provider.generate(
            system="s", prompt="p", context={}, output_type=smoke.SmokeReply
        )
    assert secret not in str(exc.value) + caplog.text

    class BadReplyClient:
        def create(self, **kwargs):
            return type(
                "Response",
                (),
                {
                    "model": smoke.MODEL,
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {
                                "message": type(
                                    "Message",
                                    (),
                                    {
                                        "content": "invalid JSON " + secret,
                                    },
                                )()
                            },
                        )(),
                    ],
                },
            )()

    client.chat.completions = BadReplyClient()
    with pytest.raises(ProviderError, match="invalid JSON") as exc:
        provider.generate(
            system="s", prompt="p", context={}, output_type=smoke.SmokeReply
        )
    assert secret not in str(exc.value) + caplog.text


def test_auth_failure_does_not_reach_api_response(monkeypatch, tmp_path):
    from axiom.config import Settings
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.axiom.api.routes import ServiceState, build_router

    secret = "private-test-key"

    class AuthClient:
        def create(self, **kwargs):
            request = httpx.Request("POST", smoke.BASE_URL + "chat/completions")
            response = httpx.Response(401, request=request)
            raise AuthenticationError(
                f"Authorization: Bearer {secret}", response=response, body=None
            )

    client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": AuthClient()})()},
    )()
    monkeypatch.setattr("backend.llm.nebius.OpenAI", lambda **kwargs: client)
    settings = Settings(
        reasoning_provider="nebius",
        nebius_api_key=secret,
        nebius_max_retries=0,
        db_path=str(tmp_path / "smoke.db"),
        artifact_root=str(tmp_path / "artifacts"),
    )
    app = FastAPI()
    app.include_router(build_router(ServiceState(settings)))
    response = TestClient(app).post(
        "/research", json={"description": "Reduce inference latency by 20%"}
    )
    assert response.status_code == 502
    assert "authentication failed" in response.text
    assert secret not in response.text
    assert "Authorization" not in response.text


def test_rate_limit_error_is_clear_and_sanitized(monkeypatch, caplog):
    secret = "private-test-key"

    class LimitedClient:
        def create(self, **kwargs):
            request = httpx.Request("POST", smoke.BASE_URL + "chat/completions")
            response = httpx.Response(429, request=request)
            raise RateLimitError(
                f"Authorization: Bearer {secret}", response=response, body=None
            )

    client = type(
        "Client",
        (),
        {
            "chat": type(
                "Chat",
                (),
                {
                    "completions": LimitedClient(),
                },
            )()
        },
    )()
    monkeypatch.setattr("backend.llm.nebius.OpenAI", lambda **kwargs: client)
    provider = NebiusLLMProvider(api_key=secret, model=smoke.MODEL, max_retries=0)
    with pytest.raises(ProviderError, match="rate limit") as exc:
        provider.generate(
            system="s", prompt="p", context={}, output_type=smoke.SmokeReply
        )
    assert secret not in str(exc.value) + caplog.text
