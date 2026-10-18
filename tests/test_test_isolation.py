"""Regression coverage for credential reloads and accidental live clients."""

import os
import socket
import subprocess
import sys

import pytest

from axiom.config import Settings
from backend.axiom.benchmarks.inference_runner import main


def test_test_defaults_are_offline():
    settings = Settings()
    assert settings.reasoning_provider == "echo"
    assert settings.executor_backend == "local"
    assert settings.nebius_api_key is None
    assert settings.db_path == ":memory:"


def test_dotenv_cannot_reload_credentials_in_child(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("NEBIUS_API_KEY=regression-fake-key\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-c", "import os, sys; from dotenv import load_dotenv; "
         "load_dotenv(sys.argv[1]); assert not os.environ.get('NEBIUS_API_KEY')", str(dotenv)],
        env=dict(os.environ), capture_output=True, text=True, encoding="utf-8", timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_missing_key_never_constructs_live_client(monkeypatch, capsys):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    def unexpected_client(*args, **kwargs):
        raise AssertionError("Missing credentials must be checked before client creation")
    monkeypatch.setattr("backend.axiom.benchmarks.inference_runner.OpenAI", unexpected_client)
    assert main(["--live", "--max-requests", "10"]) == 2
    assert "NEBIUS_API_KEY" in capsys.readouterr().err


def test_external_network_is_rejected_before_connecting():
    with socket.socket() as sock:
        with pytest.raises(AssertionError, match="Unexpected network"):
            sock.connect(("203.0.113.1", 443))
