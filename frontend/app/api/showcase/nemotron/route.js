import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MODEL = "nvidia/nemotron-3-super-120b-a12b";
const BASE_URL = "https://api.tokenfactory.nebius.com/v1/chat/completions";
const COOLDOWN_MS = 5 * 60 * 1000;
const MAX_OUTPUT_TOKENS = 500;
let lastCallAt = 0;
let cachedResult = null;

const schema = {
  type: "object",
  additionalProperties: false,
  properties: {
    hypothesis: { type: "string" },
    experiment: { type: "string" },
    metric: { type: "string" },
    safety_check: { type: "string" },
    limitation: { type: "string" },
  },
  required: ["hypothesis", "experiment", "metric", "safety_check", "limitation"],
};

function responseError(status, detail) {
  return NextResponse.json({ error: detail }, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}

export async function POST() {
  const enabled = process.env.AXIOM_NEBIUS_SHOWCASE_ENABLED === "1";
  const apiKey = process.env.NEBIUS_API_KEY;
  if (!enabled) return responseError(503, "Live Nemotron showcase is not enabled.");
  if (!apiKey) return responseError(503, "Server-side Nebius credentials are not configured.");

  const now = Date.now();
  if (now - lastCallAt < COOLDOWN_MS) {
    if (cachedResult) {
      return NextResponse.json({ ...cachedResult, cached: true }, {
        headers: { "Cache-Control": "no-store" },
      });
    }
    return responseError(429, "Please wait before requesting another model response.");
  }
  // Set before the upstream request to prevent concurrent callers from fanning out.
  lastCallAt = now;

  const prompt = [
    "You are AXIOM, an evidence-first ML experiment planning assistant.",
    "Given the fixed objective: Reduce model inference latency by 20%.",
    "Return a concise, technically sound proposal for one controlled experiment.",
    "Do not claim that any experiment has run or that any performance improvement was measured.",
    "Do not invent benchmark results. Explicitly distinguish a hypothesis from measured evidence.",
    "The safety_check must say generated code is not executed by this showcase.",
    "The limitation must state that this response is a plan, not a benchmark result.",
  ].join("\n");

  let upstream;
  try {
    upstream = await fetch(BASE_URL, {
      method: "POST",
      headers: {
        Authorization: "Bearer " + apiKey,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: MODEL,
        messages: [
          {
            role: "system",
            content: "Return only a valid JSON object matching the requested schema. Never claim unobserved measurements.",
          },
          { role: "user", content: prompt },
        ],
        temperature: 0.1,
        max_tokens: MAX_OUTPUT_TOKENS,
        response_format: {
          type: "json_schema",
          json_schema: { name: "axiom_showcase", strict: true, schema },
        },
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(20_000),
    });
  } catch {
    return responseError(502, "Nebius Token Factory could not be reached. Please try again after the cooldown.");
  }

  if (!upstream.ok) {
    // Do not forward upstream error bodies, headers, or credential details.
    return responseError(
      upstream.status === 401 || upstream.status === 403 ? 503 : 502,
      upstream.status === 401 || upstream.status === 403
        ? "Nebius authentication or model access needs attention."
        : "Nebius did not complete the showcase request.",
    );
  }

  let payload;
  try {
    payload = await upstream.json();
  } catch {
    return responseError(502, "Nebius returned an unreadable response.");
  }

  const content = payload?.choices?.[0]?.message?.content;
  let parsed;
  try {
    parsed = JSON.parse(content);
  } catch {
    return responseError(502, "Nemotron response was not valid JSON.");
  }

  for (const field of schema.required) {
    if (typeof parsed?.[field] !== "string" || !parsed[field].trim() || parsed[field].length > 1200) {
      return responseError(502, "Nemotron response did not pass output validation.");
    }
  }

  cachedResult = {
    provider: "Nebius Token Factory",
    model: payload.model || MODEL,
    result: Object.fromEntries(schema.required.map((field) => [field, parsed[field].trim()])),
    evidence_status: "model-generated proposal; no experiment executed",
    generated_at: new Date().toISOString(),
    cached: false,
  };
  return NextResponse.json(cachedResult, {
    headers: { "Cache-Control": "no-store" },
  });
}
