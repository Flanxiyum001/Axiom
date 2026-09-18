"""Nebius real API smoke test.

This script is **opt‑in** only. It will:
1. Check for required environment variables (NEBIUS_API_KEY, NEBIUS_BASE_URL, NEBIUS_MODEL).
2. If any are missing, print a helpful message and exit with status 0.
3. If configured, make a single small request to the Nebius Token Factory using the real NebiusLLMProvider.
4. Ask for a simple structured hypothesis (using the Hypothesis schema).
5. Validate the response with Pydantic and print the result.
6. No experiment execution is performed – this is purely a LLM reasoning sanity check.
"""

import os
import sys
from pathlib import Path

# Add the root directory to sys.path to allow importing backend
sys.path.append(str(Path(__file__).resolve().parents[2]))

# Load .env from the repository root before checking environment variables
from dotenv import load_dotenv
load_dotenv()

from backend.llm.nebius import NebiusLLMProvider
from backend.models.schemas import Hypothesis

def _required_env(var_name: str) -> str | None:
    return os.getenv(var_name)

def main() -> int:
    api_key = _required_env("NEBIUS_API_KEY")
    base_url = _required_env("NEBIUS_BASE_URL")
    model = _required_env("NEBIUS_MODEL")

    missing = [v for v in ["NEBIUS_API_KEY", "NEBIUS_BASE_URL", "NEBIUS_MODEL"] if not _required_env(v)]
    if missing:
        print("Nebius smoke test not configured. The following environment variables are missing:")
        for v in missing:
            print(f"  - {v}")
        print("Set them in a .env file (see .env.example) or export them before running this script.")
        return 0

    # Provider initialization – no retries to keep the demo fast
    provider = NebiusLLMProvider(
        api_key=api_key,
        base_url=base_url,
        model=model,
        request_timeout=30,
        max_retries=0,
    )

    system_prompt = "You are an AXIOM researcher. Propose a single simple hypothesis for a dummy objective. Return ONLY JSON matching the Hypothesis schema."
    user_prompt = "Generate a hypothesis that suggests increasing batch size could improve throughput."
    context = {}
    try:
        hypothesis: Hypothesis = provider.generate(
            system=system_prompt,
            prompt=user_prompt,
            context=context,
            output_type=Hypothesis,
        )
    except Exception as e:
        print(f"Nebius request failed: {e}")
        return 1

    print("✅ Received valid Hypothesis from Nebius:")
    print(hypothesis.json(indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
