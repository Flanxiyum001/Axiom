"""LLM Provider Abstraction for AXIOM.

This module provides a provider-agnostic interface for structured LLM generation,
with a deterministic mock provider for testing.
"""

from .base import LLMProvider, ProviderError
from .mock import MockLLMProvider

__all__ = [
    "LLMProvider",
    "ProviderError",
    "MockLLMProvider",
]