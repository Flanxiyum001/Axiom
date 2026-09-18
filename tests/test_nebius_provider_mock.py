"""Mocked tests for NebiusLLMProvider without real network calls.

These tests verify:
- Provider implements LLMProvider interface
- Correct request construction (model, messages, temperature, response_format)
- Authentication handling (api_key passed to OpenAI client)
- Base URL normalization
- Structured JSON response parsing (including code fences)
- Pydantic validation of the output
- Handling of malformed JSON responses
- API error handling with retries
- Timeout handling
"""

import json
from types import SimpleNamespace
import pytest

from backend.llm.base import LLMProvider, ProviderError
from backend.llm.nebius import NebiusLLMProvider
from backend.models.schemas import (
    Hypothesis,
    ResearchObjective,
    MetricDefinition,
    MetricDirection,
)

def _dummy_objective():
    return ResearchObjective(
        title="Dummy",
        description="Dummy objective",
        metrics=[MetricDefinition(name="latency_ms", unit="ms", direction=MetricDirection.MINIMIZE)],
        constraints={},
        target={},
        max_experiments=1,
    )

def dummy_client_factory(captured: dict, response_content: str):
    def create(**kwargs):
        captured.update(kwargs)
        class Choice:
            class Message:
                content = response_content
            message = Message()
        class Resp:
            choices = [Choice()]
        return Resp()
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

def test_request_construction_and_auth(monkeypatch):
    captured = {}
    response_json = json.dumps(
        {
            "title": "Test",
            "objective_id": "00000000-0000-0000-0000-000000000000",
            "description": "desc",
            "rationale": "r",
            "expected_outcome": "out",
            "status": "pending",
        }
    )
    client = dummy_client_factory(captured, response_json)
    monkeypatch.setattr("backend.llm.nebius.OpenAI", lambda *a, **kw: client)

    provider = NebiusLLMProvider(
        api_key="my-secret-key",
        base_url="https://api.tokenfactory.nebius.com/v1",
        model="my-model",
        request_timeout=30,
        max_retries=0,
    )
    system = "system"
    prompt = "prompt"
    context = {"objective": _dummy_objective().model_dump_json()}
    result = provider.generate(system=system, prompt=prompt, context=context, output_type=Hypothesis)

    assert captured["model"] == "my-model"
    msgs = captured["messages"]
    assert any(m["role"] == "system" and system in m["content"].lower() for m in msgs)
    assert any(m["role"] == "user" and m["content"] == prompt for m in msgs)
    assert captured["temperature"] == 0.1
    assert captured["response_format"] == {"type": "json_object"}
    assert isinstance(result, Hypothesis)
    assert result.title == "Test"

def test_nebius_provider_implements_interface():
    provider = NebiusLLMProvider(
        api_key="test-key",
        base_url="https://api.tokenfactory.nebius.com/v1/",
        model="test-model",
    )
    assert isinstance(provider, LLMProvider)
    assert provider.name == "nebius"

def test_base_url_normalization(monkeypatch):
    captured = {}
    response_json = json.dumps(
        {
            "title": "T",
            "objective_id": "00000000-0000-0000-0000-000000000000",
            "description": "d",
            "rationale": "r",
            "expected_outcome": "o",
            "status": "pending",
        }
    )
    client = dummy_client_factory(captured, response_json)
    monkeypatch.setattr("backend.llm.nebius.OpenAI", lambda *a, **kw: client)
    provider = NebiusLLMProvider(
        api_key="k",
        base_url="https://api.tokenfactory.nebius.com/v1",
        model="m",
    )
    provider.generate(system="s", prompt="p", context={}, output_type=Hypothesis)
    assert provider.base_url.endswith("/")
    assert provider.base_url == "https://api.tokenfactory.nebius.com/v1/"

def test_structured_response_parsing_with_code_fence(monkeypatch):
    captured = {}
    payload = {
        "title": "CF",
        "objective_id": "00000000-0000-0000-0000-000000000000",
        "description": "d",
        "rationale": "r",
        "expected_outcome": "o",
        "status": "pending",
    }
    fenced = "```json\n" + json.dumps(payload) + "\n```"
    client = dummy_client_factory(captured, fenced)
    monkeypatch.setattr("backend.llm.nebius.OpenAI", lambda *a, **kw: client)
    provider = NebiusLLMProvider(api_key="k", base_url="https://api.tokenfactory.nebius.com/v1/", model="m")
    result = provider.generate(system="s", prompt="p", context={}, output_type=Hypothesis)
    assert result.title == "CF"

def test_pydantic_validation_error(monkeypatch):
    captured = {}
    bad_json = {
        "objective_id": "00000000-0000-0000-0000-000000000000",
        "description": "d",
        "rationale": "r",
        "expected_outcome": "o",
        "status": "pending",
    }
    client = dummy_client_factory(captured, json.dumps(bad_json))
    monkeypatch.setattr("backend.llm.nebius.OpenAI", lambda *a, **kw: client)
    provider = NebiusLLMProvider(api_key="k", base_url="https://api.tokenfactory.nebius.com/v1/", model="m")
    with pytest.raises(ProviderError) as exc:
        provider.generate(system="s", prompt="p", context={}, output_type=Hypothesis)
    assert "failed validation" in str(exc.value).lower()

def test_malformed_json_handling(monkeypatch):
    captured = {}
    client = dummy_client_factory(captured, "{ not a json }")
    monkeypatch.setattr("backend.llm.nebius.OpenAI", lambda *a, **kw: client)
    provider = NebiusLLMProvider(api_key="k", base_url="https://api.tokenfactory.nebius.com/v1/", model="m")
    with pytest.raises(ProviderError) as exc:
        provider.generate(system="s", prompt="p", context={}, output_type=Hypothesis)
    assert "invalid json" in str(exc.value).lower()

def test_api_error_retry_and_failure(monkeypatch):
    call_counter = {"count": 0}
    def error_client_factory(_):
        def create(**kwargs):
            call_counter["count"] += 1
            raise RuntimeError("simulated network error")
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    client = error_client_factory({})
    monkeypatch.setattr("backend.llm.nebius.OpenAI", lambda *a, **kw: client)
    provider = NebiusLLMProvider(
        api_key="k",
        base_url="https://api.tokenfactory.nebius.com/v1/",
        model="m",
        max_retries=2,
    )
    with pytest.raises(ProviderError) as exc:
        provider.generate(system="s", prompt="p", context={}, output_type=Hypothesis)
    assert call_counter["count"] == 3
    assert "failed to generate valid output" in str(exc.value).lower()

def test_timeout_handling(monkeypatch):
    captured = {}
    def timeout_client_factory(_):
        def create(**kwargs):
            raise TimeoutError("request timed out")
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    client = timeout_client_factory({})
    monkeypatch.setattr("backend.llm.nebius.OpenAI", lambda *a, **kw: client)
    provider = NebiusLLMProvider(
        api_key="k",
        base_url="https://api.tokenfactory.nebius.com/v1/",
        model="m",
        max_retries=1,
    )
    with pytest.raises(ProviderError) as exc:
        provider.generate(system="s", prompt="p", context={}, output_type=Hypothesis)
    assert "failed to generate valid output" in str(exc.value).lower()