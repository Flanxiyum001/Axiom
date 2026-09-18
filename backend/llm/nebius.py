"""Nebius Token Factory LLM Provider for AXIOM.

This provider uses the Nebius Token Factory OpenAI-compatible API to run
real Nemotron models while maintaining the structured output contract
required by AXIOM agents.
"""

import json
import time
import logging
from typing import TypeVar, Dict, Any, Optional

from openai import OpenAI
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
        api_key: Optional[str] = None,
        base_url: str = "https://api.tokenfactory.nebius.com/v1/",
        model: str = "meta-llama/Meta-Llama-3.1-70B-Instruct",
        request_timeout: float = 60.0,
        max_retries: int = 3,
        seed: Optional[int] = None,
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

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.request_timeout,
            max_retries=0,
        )

        logger.info(
            f"Initialized NebiusLLMProvider with model={self.model}, "
            f"base_url={self.base_url}"
        )

    def _truncate_context(self, context: Dict[str, str], max_chars: int = 8000) -> Dict[str, str]:
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
        self, system: str, prompt: str, context: Dict[str, str]
    ) -> list[Dict[str, str]]:
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

    def _validate_and_parse_response(
        self, content: str, output_type: type[T]
    ) -> T:
        """Validate and parse the model response into the requested Pydantic model."""
        if not content or not content.strip():
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
            logger.error(f"Failed to parse JSON from model response: {content}")
            raise ProviderError(
                f"Model returned invalid JSON: {str(e)}. "
                f"Response: {content[:200]}..."
            ) from e

        try:
            return output_type.model_validate(data)
        except ValidationError as e:
            logger.error(f"Pydantic validation failed for data: {data}")
            raise ProviderError(
                f"Model response failed validation: {str(e)}. "
                f"Data: {json.dumps(data, indent=2)[:500]}..."
            ) from e

    def generate(
        self,
        *,
        system: str,
        prompt: str,
        context: Dict[str, str],
        output_type: type[T],
    ) -> T:
        """Generate a validated instance of output_type from the prompt."""
        truncated_context = self._truncate_context(context)
        messages = self._build_messages(system, prompt, truncated_context)

        request_params = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        if self.seed is not None:
            request_params["seed"] = self.seed

        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(
                    f"Nebius API call attempt {attempt + 1}/{self.max_retries + 1}"
                )

                response: ChatCompletion = self.client.chat.completions.create(
                    **request_params
                )

                content = response.choices[0].message.content
                if content is None:
                    raise ProviderError("Model returned empty content")

                result = self._validate_and_parse_response(content, output_type)

                logger.debug(
                    f"Successfully generated {output_type.__name__} from Nebius API"
                )
                return result

            except Exception as e:
                # Do not retry on validation or permanent client errors
                from openai import BadRequestError, AuthenticationError, NotFoundError, UnprocessableEntityError, APIError, RateLimitError, APIConnectionError

                # If it's our own ProviderError (validation, parsing), re‑raise immediately
                if isinstance(e, ProviderError):
                    raise

                # Permanent client errors (4xx except 429) should not be retried
                permanent_errors = (BadRequestError, AuthenticationError, NotFoundError, UnprocessableEntityError)
                if isinstance(e, permanent_errors):
                    raise ProviderError(str(e)) from e

                # OpenAI APIError may contain a status_code; retry on 5xx or 429
                if isinstance(e, APIError):
                    status = getattr(e, "status_code", None)
                    if status and (500 <= status < 600 or status == 429):
                        # transient – allow retry below
                        pass
                    else:
                        raise ProviderError(str(e)) from e

                # Rate limit or connection issues are transient
                if isinstance(e, (RateLimitError, APIConnectionError, TimeoutError, OSError)):
                    # transient – allow retry below
                    pass
                else:
                    # Any other unexpected exception – treat as transient for now
                    pass

                last_exception = e
                logger.warning(
                    f"Nebius API call failed (attempt {attempt + 1}): {str(e)}"
                )

                if attempt < self.max_retries:
                    wait_time = 2**attempt
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)

        error_msg = (
            f"Failed to generate valid output after {self.max_retries + 1} attempts. "
            f"Last error: {str(last_exception)}"
        )
        logger.error(error_msg)
        raise ProviderError(error_msg) from last_exception