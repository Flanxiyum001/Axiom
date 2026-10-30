"""Nebius Token Factory LLM Provider for AXIOM.

This provider uses the Nebius Token Factory OpenAI-compatible API to run
real Nemotron models while maintaining the structured output contract
required by AXIOM agents.
"""

import json
import logging
import time
from typing import TypeVar

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
    UnprocessableEntityError,
)
from openai.types.chat import ChatCompletion
from pydantic import BaseModel, ValidationError

from .base import LLMProvider, ProviderError

logger = logging.getLogger("axiom.llm.nebius")

T = TypeVar("T", bound=BaseModel)


class NebiusLLMProvider(LLMProvider):
    """Nebius Token Factory provider using OpenAI-compatible API."""

    name = "nebius"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.tokenfactory.nebius.com/v1/",
        model: str = "meta-llama/Meta-Llama-3.1-70B-Instruct",
        request_timeout: float = 60.0,
        max_retries: int = 3,
        seed: int | None = None,
    ):
        """Initialize the Nebius provider."""
        from ..config import settings

        self.api_key = api_key or settings.nebius_api_key
        if not self.api_key:
            raise ProviderError(
                "Nebius API key not configured. Set NEBIUS_API_KEY environment variable."
            )

        self.base_url = base_url.rstrip("/") + "/"
        self.model = model
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.seed = seed
        self.last_response_model: str | None = None

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.request_timeout,
            max_retries=0,
        )

        logger.info("Initialized NebiusLLMProvider with model=%s", self.model)

    def _truncate_context(
        self, context: dict[str, str], max_chars: int = 8000
    ) -> dict[str, str]:
        """Truncate context values to prevent excessive prompt sizes."""
        truncated = {}
        total_chars = 0

        for key, value in context.items():
            value_chars = len(value)
            if total_chars + value_chars > max_chars:
                remaining = max_chars - total_chars
                if remaining > 50:
                    truncated[key] = value[:remaining] + "...[truncated]"
                else:
                    truncated[key] = "[context truncated due to size limits]"
                break
            else:
                truncated[key] = value
                total_chars += value_chars

        return truncated

    def _build_messages(
        self, system: str, prompt: str, context: dict[str, str]
    ) -> list[dict[str, str]]:
        """Build the messages array for the chat completion API."""
        messages = []

        if system.strip():
            messages.append({"role": "system", "content": system})

        if context:
            context_str = json.dumps(context, indent=2)
            messages.append(
                {
                    "role": "system",
                    "content": f"Context (JSON):\n{context_str}",
                }
            )

        messages.append({"role": "user", "content": prompt})

        return messages

    def _validate_and_parse_response(self, content: str, output_type: type[T]) -> T:
        """Validate and parse the model response into the requested Pydantic model."""
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("Empty response from model")

        try:
            if content.strip().startswith("```"):
                lines = content.strip().split("\n")
                json_lines = []
                in_code_block = False
                for line in lines:
                    if line.strip().startswith("```"):
                        in_code_block = not in_code_block
                        continue
                    if in_code_block:
                        json_lines.append(line)
                content = "\n".join(json_lines)

            data = json.loads(content.strip())
        except json.JSONDecodeError as e:
            raise ProviderError("Model returned invalid JSON") from e

        try:
            return output_type.model_validate(data)
        except ValidationError as e:
            raise ProviderError("Model response failed validation") from e

    def _build_response_format(self, output_type: type[T]) -> dict:
        """Build the response_format parameter for structured output using JSON Schema."""
        # Use Pydantic's model_json_schema to get the schema
        schema = output_type.model_json_schema()
        return {
            "type": "json_schema",
            "json_schema": {
                "name": output_type.__name__,
                "schema": schema,
                "strict": True,
            },
        }

    def generate(
        self,
        *,
        system: str,
        prompt: str,
        context: dict[str, str],
        output_type: type[T],
    ) -> T:
        """Generate a validated instance of output_type from the prompt."""
        truncated_context = self._truncate_context(context)
        messages = self._build_messages(system, prompt, truncated_context)

        request_params = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "response_format": self._build_response_format(output_type),
        }

        if self.seed is not None:
            request_params["seed"] = self.seed

        self.last_response_model = None
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(
                    f"Nebius API call attempt {attempt + 1}/{self.max_retries + 1}"
                )

                response: ChatCompletion = self.client.chat.completions.create(
                    **request_params
                )

                self.last_response_model = getattr(response, "model", None)
                content = response.choices[0].message.content
                if content is None:
                    raise ProviderError("Model returned empty content")

                result = self._validate_and_parse_response(content, output_type)

                logger.debug(
                    f"Successfully generated {output_type.__name__} from Nebius API"
                )
                return result

            except Exception as e:
                # If it's our own ProviderError (validation, parsing), re‑raise immediately
                if isinstance(e, ProviderError):
                    raise

                if isinstance(e, (AuthenticationError, PermissionDeniedError)):
                    raise ProviderError(
                        f"Nebius authentication failed (HTTP {e.status_code}); check NEBIUS_API_KEY"
                    ) from None
                if isinstance(
                    e, (BadRequestError, NotFoundError, UnprocessableEntityError)
                ):
                    raise ProviderError(
                        f"Nebius rejected the request (HTTP {e.status_code}); check model and schema"
                    ) from None
                if isinstance(e, RateLimitError):
                    error_message = "Nebius rate limit reached (HTTP 429)"
                elif isinstance(e, (APITimeoutError, TimeoutError)):
                    error_message = "Nebius request timed out"
                elif isinstance(e, (APIConnectionError, OSError)):
                    error_message = "Could not connect to Nebius Token Factory"
                elif isinstance(e, APIError):
                    status = getattr(e, "status_code", None)
                    if status is None or not (500 <= status < 600):
                        raise ProviderError("Nebius request failed") from None
                    error_message = f"Nebius server error (HTTP {status})"
                else:
                    error_message = "Nebius returned a malformed or unexpected response"
                logger.warning(
                    "%s (attempt %s/%s)",
                    error_message,
                    attempt + 1,
                    self.max_retries + 1,
                )

                if attempt < self.max_retries:
                    wait_time = 2**attempt
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)

        error_msg = f"Failed to generate valid output after {self.max_retries + 1} attempts: {error_message}"
        logger.error(error_msg)
        raise ProviderError(error_msg) from None
