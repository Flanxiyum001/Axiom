"""Tests for LLM provider selection and Nebius provider.

These tests verify:
- Default provider is mock (deterministic, no API key needed)
- Nebius provider can be instantiated with API key
- Nebius provider raises error when API key is missing
- Provider selection in orchestrator works correctly
"""

import pytest
import os
from backend.config import settings
from backend.llm.mock import MockLLMProvider
from backend.llm.base import LLMProvider, ProviderError


def test_default_provider_is_mock():
    """Test that default AXIOM_LLM_PROVIDER is mock."""
    # Reset settings to defaults (without env override)
    from pydantic_settings import BaseSettings

    # Create fresh settings without env file
    original = settings.axiom_llm_provider
    assert original == "mock"


def test_mock_provider_implements_interface():
    """Test that MockLLMProvider implements the LLMProvider interface."""
    provider = MockLLMProvider()
    assert isinstance(provider, LLMProvider)
    assert provider.name == "mock"


def test_nebius_provider_requires_api_key():
    """Test that NebiusLLMProvider raises error when API key is missing."""
    from backend.llm.nebius import NebiusLLMProvider

    # Create provider without API key - should raise ProviderError
    with pytest.raises(ProviderError) as exc_info:
        provider = NebiusLLMProvider(
            api_key=None,
            base_url="https://api.tokenfactory.nebius.com/v1/",
            model="meta-llama/Meta-Llama-3.1-70B-Instruct",
        )
    assert "Nebius API key not configured" in str(exc_info.value)


def test_nebius_provider_with_api_key():
    """Test that NebiusLLMProvider can be instantiated with API key."""
    from backend.llm.nebius import NebiusLLMProvider

    # Create provider with explicit API key
    provider = NebiusLLMProvider(
        api_key="test-api-key",
        base_url="https://api.tokenfactory.nebius.com/v1/",
        model="meta-llama/Meta-Llama-3.1-70B-Instruct",
    )
    assert provider.name == "nebius"
    assert provider.model == "meta-llama/Meta-Llama-3.1-70B-Instruct"
    assert provider.base_url == "https://api.tokenfactory.nebius.com/v1/"
    assert provider.api_key == "test-api-key"


def test_nebius_provider_base_url_trailing_slash():
    """Test that base URL is normalized with trailing slash."""
    from backend.llm.nebius import NebiusLLMProvider

    provider = NebiusLLMProvider(
        api_key="test-key",
        base_url="https://api.tokenfactory.nebius.com/v1",
        model="test-model",
    )
    assert provider.base_url == "https://api.tokenfactory.nebius.com/v1/"


def test_orchestrator_uses_mock_by_default():
    """Test that Orchestrator uses MockLLMProvider by default."""
    from backend.orchestrator import Orchestrator
    from backend.models.schemas import (
        ResearchObjective,
        MetricDefinition,
        MetricDirection,
    )

    objective = ResearchObjective(
        title="Test",
        description="Test objective",
        metrics=[
            MetricDefinition(
                name="accuracy", unit="ratio", direction=MetricDirection.MAXIMIZE
            )
        ],
        constraints={},
        target={},
        max_experiments=1,
    )

    orchestrator = Orchestrator(objective, baseline={"accuracy": 0.95})
    assert isinstance(orchestrator.provider, MockLLMProvider)
    assert orchestrator.provider.name == "mock"


def test_orchestrator_uses_nebius_when_configured():
    """Test that Orchestrator uses NebiusLLMProvider when configured."""
    from backend.orchestrator import Orchestrator
    from backend.models.schemas import (
        ResearchObjective,
        MetricDefinition,
        MetricDirection,
    )
    from backend.llm.nebius import NebiusLLMProvider

    # Temporarily set provider to nebius and provide API key
    original_provider = settings.axiom_llm_provider
    original_api_key = settings.nebius_api_key
    try:
        # Override settings
        settings.axiom_llm_provider = "nebius"
        settings.nebius_api_key = "test-api-key"

        objective = ResearchObjective(
            title="Test",
            description="Test objective",
            metrics=[
                MetricDefinition(
                    name="accuracy", unit="ratio", direction=MetricDirection.MAXIMIZE
                )
            ],
            constraints={},
            target={},
            max_experiments=1,
        )

        orchestrator = Orchestrator(objective, baseline={"accuracy": 0.95})
        assert isinstance(orchestrator.provider, NebiusLLMProvider)
        assert orchestrator.provider.name == "nebius"
    finally:
        settings.axiom_llm_provider = original_provider
        settings.nebius_api_key = original_api_key