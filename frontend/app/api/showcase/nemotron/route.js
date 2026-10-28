import { NextResponse } from "next/server";
import { BASE_URL, MODEL, buildNemotronRequest, parseNemotronContent } from "../../../../lib/nemotron-showcase.mjs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const COOLDOWN_MS = 5 * 60 * 1000;
let lastCallAt = 0;
let cachedResult = null;

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
  lastCallAt = now;

  let upstream;
  try {
    upstream = await fetch(BASE_URL, {
      method: "POST",
      headers: {
        Authorization: "Bearer " + apiKey,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(buildNemotronRequest()),
      cache: "no-store",
      signal: AbortSignal.timeout(20_000),
    });
  } catch {
    return responseError(502, "Nebius Token Factory could not be reached. Please try again after the cooldown.");
  }

  if (!upstream.ok) {
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

  let result;
  try {
    result = parseNemotronContent(payload?.choices?.[0]?.message?.content);
  } catch (error) {
    return responseError(502, error instanceof Error ? error.message : "Nemotron response validation failed.");
  }

  cachedResult = {
    provider: "Nebius Token Factory",
    model: payload.model || MODEL,
    result,
    evidence_status: "model-generated proposal; no experiment executed",
    generated_at: new Date().toISOString(),
    cached: false,
  };
  return NextResponse.json(cachedResult, {
    headers: { "Cache-Control": "no-store" },
  });
}
