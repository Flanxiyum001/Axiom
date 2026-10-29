# Live Nemotron showcase

The standalone route at `/showcase` calls the NVIDIA Nemotron 3 Super model through Nebius Token Factory from the Next.js server. It uses a fixed prompt and validates five required string fields. It does not accept user prompts, run generated code, or claim benchmark results.

## Required server-side environment

Set these variables on the **frontend Railway service**, not in browser-visible variables:

- `AXIOM_NEBIUS_SHOWCASE_ENABLED=1`
- `NEBIUS_API_KEY=<secret>`

The model ID and Token Factory URL are pinned in the server route. Never use a `NEXT_PUBLIC_` prefix for the API key. Never paste the key into GitHub, this chat, a video, or submission text.

## Controls and limits

- Fixed prompt; no arbitrary input.
- Maximum output of 500 tokens and a 20-second timeout.
- Five-minute per-process cooldown, with successful response caching.
- Server-side errors are sanitized; upstream error bodies and credentials are never returned.
- Structured output is parsed and field-validated.
- No generated code is executed and no experimental metric is fabricated.

The cooldown is an in-memory best-effort limit, not a distributed quota system. Serverless instances can scale independently. Keep the feature disabled until the key and quota are verified, and use provider-side usage limits where available. A live model response proves model integration, not that the full research loop or a real inference optimization has been demonstrated.
