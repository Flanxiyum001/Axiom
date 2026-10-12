# AXIOM Research Dashboard

A minimal Next.js dashboard for the existing AXIOM FastAPI service. It can check the API connection, create and list research objectives, run a bounded research loop, and inspect hypothesis, evaluation metrics, analyst evidence, and stored history.

## Requirements

- Python 3.11 or newer for the backend
- Node.js 20.9 or newer for the frontend
- Local API configuration; use the mock/echo provider for offline development or configure Nebius Token Factory for live reasoning

## Start locally

From the repository root, install and start the backend:

~~~bash
python -m pip install -e '.[dev]'
uvicorn backend.main:app --reload
~~~

In a second terminal:

~~~bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
~~~

Open http://localhost:3000. The default backend URL is http://127.0.0.1:8000. The dashboard checks /health and then reads objectives from the API.

## Live Nemotron reasoning

For real model-generated research reasoning, configure the backend's local .env or environment:

~~~dotenv
AXIOM_REASONING_PROVIDER=nebius
NEBIUS_API_KEY=your_rotated_key_here
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/
NEBIUS_MODEL=nvidia/nemotron-3-super-120b-a12b
~~~

Never commit .env or put credentials in a NEXT_PUBLIC variable. The frontend does not need the API key; it only calls the backend.

## CORS

The backend allows two local dashboard origins by default: http://localhost:3000 and http://127.0.0.1:3000. For deployment, set AXIOM_CORS_ORIGINS to a comma-separated list of exact trusted frontend origins, for example:

~~~dotenv
AXIOM_CORS_ORIGINS=https://your-dashboard.example
~~~

Do not use a wildcard for a deployed dashboard. CORS only controls browser access; it is not authentication. Do not expose a public backend to untrusted users until authentication, rate limits, and resource limits are configured.

## Current scope and limitations

- One to three iterations can be selected from the UI to keep demonstration runs bounded.
- Runs use the backend's configured executor; this dashboard does not imply that Nebius AI Cloud GPU execution is verified.
- Local reports under artifacts/benchmarks/ are not automatically uploaded or displayed here.
- This is a demo-first dashboard and does not yet provide authentication, multi-user tenancy, deployment configuration, or editing/deleting objectives.
