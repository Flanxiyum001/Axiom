import { NextResponse } from "next/server";
import { BASE_URL, buildNemotronRequest, parseNemotronContent, verifyNemotronModel, isCrossSiteShowcaseRequest, describeNemotronResponse } from "../../../../lib/nemotron-showcase.mjs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const COOLDOWN_MS = 5 * 60 * 1000;
let lastCallAt = 0;
let cachedResult = null;

function emitProviderDiagnostic({ status = null, contentType = null, payload = null, condition }) {
  // Provider response text and credentials must never reach application logs.
  console.warn("AXIOM_NEMOTRON_RESPONSE", JSON.stringify(describeNemotronResponse({
    upstreamStatus: status,
    responseContentType: contentType,
    payload,
    condition,
  })));
}

function responseError(status, detail) {
  return NextResponse.json({ error: detail }, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}

export async function POST(request) {
  if (isCrossSiteShowcaseRequest(request?.headers)) {
    return responseError(403, "Cross-site model requests are not permitted.");
  }
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
    emitProviderDiagnostic({ condition: "upstream_network_or_timeout" });
    return responseError(502, "Nebius Token Factory could not be reached. Please try again after the cooldown.");
  }

  const upstreamType = upstream.headers.get("content-type");
  if (!upstream.ok) {
    emitProviderDiagnostic({ status: upstream.status, contentType: upstreamType, condition: "upstream_http_error" });
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
    emitProviderDiagnostic({ status: upstream.status, contentType: upstreamType, condition: "upstream_non_json" });
    return responseError(502, "Nebius returned an unreadable response.");
  }

  let result;
  let verifiedModel;
  try {
    verifiedModel = verifyNemotronModel(payload?.model);
    const finishReason = payload?.choices?.[0]?.finish_reason;
    // A truncated/refused/unfinished response must never be represented as
    // a complete experiment proposal, even if its partial JSON parses.
    if (finishReason !== "stop") {
      emitProviderDiagnostic({
        status: upstream.status, contentType: upstreamType, payload,
        condition: finishReason === "length" ? "output_truncated" : "finish_reason_not_stop",
      });
      return responseError(502, "Nemotron did not finish generating a complete experiment proposal.");
    }
    result = parseNemotronContent(payload?.choices?.[0]?.message?.content);
  } catch (error) {
    emitProviderDiagnostic({
      status: upstream.status, contentType: upstreamType, payload,
      condition: error?.condition || (error?.message?.includes("model identifier") ? "model_mismatch" : "validation_error"),
    });
    return responseError(502, error instanceof Error ? error.message : "Nemotron response validation failed.");
  }

  cachedResult = {
    provider: "Nebius Token Factory",
    model: verifiedModel,
    result,
    evidence_status: "model-generated proposal; no experiment executed",
    generated_at: new Date().toISOString(),
    cached: false,
  };
  return NextResponse.json(cachedResult, {
    headers: { "Cache-Control": "no-store" },
  });
}
