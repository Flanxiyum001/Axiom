"""Nebius IAM authentication for the real GPU job client.

Supports:
- Static access token (developer / local)
- Environment variable token

This module is intentionally minimal.  It does NOT use the Nebius Token
Factory API key (NEBIUS_API_KEY), which is used for LLM access.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class NebiusAuthProvider(ABC):
    """Abstract provider of Nebius IAM access tokens."""

    @abstractmethod
    def get_access_token(self) -> str:
        """Return a valid Bearer access token."""
        raise NotImplementedError


class StaticTokenProvider(NebiusAuthProvider):
    """Wraps a pre-existing IAM access token."""

    def __init__(self, token: str) -> None:
        self._token = token

    def get_access_token(self) -> str:
        return self._token


class EnvTokenProvider(NebiusAuthProvider):
    """Reads an IAM access token from the environment."""

    def __init__(self, env_var: str = "NEBIUS_IAM_TOKEN") -> None:
        self.env_var = env_var

    def get_access_token(self) -> str:
        token = os.environ.get(self.env_var)
        if not token:
            raise RuntimeError(
                f"{self.env_var} environment variable is not set"
            )
        return token


def get_provider() -> NebiusAuthProvider:
    """Default factory: uses EnvTokenProvider."""
    return EnvTokenProvider()