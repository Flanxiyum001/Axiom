"""Offline test defaults, installed before application modules are imported."""

import os
import socket

import pytest


# dotenv is also called during module collection and by child processes.
# Keep this flag for the entire pytest process, including subprocesses.
_session_env = pytest.MonkeyPatch()
_session_env.setenv("PYTHON_DOTENV_DISABLED", "1")
for name in tuple(os.environ):
    if name.startswith(("NEBIUS_", "AXIOM_")):
        _session_env.delenv(name)
for name, value in {"AXIOM_REASONING_PROVIDER": "echo", "AXIOM_EXECUTOR_BACKEND": "local",
                    "AXIOM_DB_PATH": ":memory:",
                    "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}.items():
    _session_env.setenv(name, value)


def pytest_unconfigure(config):
    _session_env.undo()


@pytest.fixture(autouse=True)
def offline_environment(monkeypatch, tmp_path):
    """Each test owns its configuration; provider tests must inject clients."""
    for name in tuple(os.environ):
        if name.startswith(("NEBIUS_", "AXIOM_")):
            monkeypatch.delenv(name)
    monkeypatch.setenv("AXIOM_REASONING_PROVIDER", "echo")
    monkeypatch.setenv("AXIOM_EXECUTOR_BACKEND", "local")
    monkeypatch.setenv("AXIOM_DB_PATH", ":memory:")
    monkeypatch.setenv("AXIOM_ARTIFACT_ROOT", str(tmp_path / "artifacts"))

    def guarded(original):
        def connect(sock, address):
            # Windows asyncio implements socketpair using loopback TCP.
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("Unexpected network connection: inject a mocked client")
        return connect

    monkeypatch.setattr(socket.socket, "connect", guarded(socket.socket.connect))
    monkeypatch.setattr(socket.socket, "connect_ex", guarded(socket.socket.connect_ex))
