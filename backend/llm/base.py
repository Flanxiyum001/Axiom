"""Abstract LLM Provider Interface for AXIOM.

This module defines the provider-agnostic interface for structured generation.
Agents depend on this abstraction, not on any specific SDK or HTTP client.
"""

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ProviderError(RuntimeError):
    """Raised when a provider cannot produce valid output."""
    pass


class LLMProvider(ABC):
    """Abstraction over an LLM that produces validated structured output.

    Implementations (mock, OpenAI-compatible, Nebius Token Factory, etc.) must:
    - Accept system prompt, user prompt, context, and output type
    - Call the model and parse the reply
    - Validate against the requested Pydantic type
    - Retry with error feedback on validation failures
    - Raise ProviderError when no valid output can be produced
    """

    name: str

    @abstractmethod
    def generate(
        self,
        *,
        system: str,
        prompt: str,
        context: dict[str, str],
        output_type: type[T],
    ) -> T:
        """Produce a validated instance of ``output_type`` from the prompt.

        Args:
            system: System prompt defining the agent's role and behavior.
            prompt: User prompt with the specific task.
            context: Key-value context carrying research state as simple strings
                     (serialized domain objects).
            output_type: Pydantic model class to validate the output against.

        Returns:
            Validated instance of ``output_type``.

        Raises:
            ProviderError: When no valid output can be produced.
        """
        raise NotImplementedError