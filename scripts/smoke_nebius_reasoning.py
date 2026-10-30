"""Opt-in, single-request check of canonical Nemotron reasoning. No code execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from axiom.config import Settings
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

from backend.llm.base import ProviderError
from backend.llm.nebius import NebiusLLMProvider

MODEL = "nvidia/nemotron-3-super-120b-a12b"
BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
MARKER = "AXIOM_NEMOTRON_OK"


class SmokeReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str


def run() -> None:
    # Read only this working tree's .env; exported variables retain precedence.
    load_dotenv(Path.cwd() / ".env", override=False)
    try:
        settings = Settings(nebius_max_retries=0)
    except ValueError:
        raise ProviderError("Invalid Nebius configuration") from None
    if not settings.nebius_api_key:
        raise ProviderError(
            "NEBIUS_API_KEY is missing; set it in the environment or local .env"
        )
    if settings.nebius_base_url.rstrip("/") + "/" != BASE_URL:
        raise ProviderError(
            "NEBIUS_BASE_URL must be the Nebius Token Factory v1 endpoint for this smoke test"
        )
    if settings.nebius_model != MODEL:
        raise ProviderError(
            f"NEBIUS_MODEL must be {MODEL} for this Nemotron smoke test"
        )

    provider = NebiusLLMProvider(
        api_key=settings.nebius_api_key,
        base_url=settings.nebius_base_url,
        model=settings.nebius_model,
        request_timeout=settings.nebius_request_timeout,
        max_retries=0,
    )
    reply = provider.generate(
        system="Return a JSON object with only the message field.",
        prompt=f"Set message to exactly {MARKER}.",
        context={},
        output_type=SmokeReply,
    )
    if provider.last_response_model != MODEL:
        raise ProviderError(
            "Nebius response did not identify the configured Nemotron model"
        )
    if reply.message != MARKER:
        raise ProviderError(
            "Nemotron response was valid JSON but failed the smoke reply check"
        )

    print(
        json.dumps(
            {
                "provider": provider.name,
                "requested_model": MODEL,
                "response_model": provider.last_response_model,
                "validated": True,
            }
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="send one real Token Factory request"
    )
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("--live is required; this command never runs in normal tests")
    try:
        run()
    except ProviderError as exc:
        print(f"Nebius smoke test failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
