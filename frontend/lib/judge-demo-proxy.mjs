import { isIP } from "node:net";

const WINDOW_MS = 60_000;
const MAX_TOTAL_REQUESTS = 180;
const MAX_TOTAL_MUTATIONS = 30;
const MAX_CLIENT_REQUESTS = 60;
const MAX_CLIENT_MUTATIONS = 6;
const MAX_BODY_BYTES = 2_048;
const MAX_BODY_CHUNKS = 16;
const MAX_RESPONSE_BYTES = 512 * 1_024;

const ALLOWED_ROUTES = [
  ["GET", /^\/health$/],
  ["GET", /^\/objectives$/],
  ["POST", /^\/objectives$/],
  ["GET", /^\/objectives\/[A-Za-z0-9_-]{1,128}$/],
  ["GET", /^\/objectives\/[A-Za-z0-9_-]{1,128}\/history$/],
  ["POST", /^\/objectives\/[A-Za-z0-9_-]{1,128}\/run$/],
];

function jsonResponse(status, detail) {
  return Response.json({ detail }, { status, headers: { "cache-control": "no-store" } });
}

function clientKey(request) {
  const forwarded = request.headers.get("x-forwarded-for");
  const candidates = forwarded ? forwarded.split(",").map((item) => item.trim()) : [];
  const ip = candidates.at(-1);
  // This is only an additional fairness limit; the global limit remains active
  // if the ingress does not provide a valid client IP.
  return ip && isIP(ip) ? ip : "unknown";
}

async function readBoundedBody(request) {
  const declared = Number(request.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > MAX_BODY_BYTES) return null;
  if (!request.body) return new Uint8Array();
  const reader = request.body.getReader();
  const chunks = [];
  let total = 0;
  let count = 0;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      count += 1;
      total += value.byteLength;
      if (total > MAX_BODY_BYTES || count > MAX_BODY_CHUNKS) {
        await reader.cancel("AXIOM demo body limit");
        return null;
      }
      chunks.push(value);
    }
  } catch {
    await reader.cancel().catch(() => {});
    throw new Error("Could not read request body");
  }

  const body = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
}

export function createJudgeDemoProxy({
  fetchImpl = fetch,
  env = process.env,
  now = () => Date.now(),
} = {}) {
  let windowStart = now();
  let totalRequests = 0;
  let totalMutations = 0;
  const clients = new Map();

  function admit(request, mutation) {
    const current = now();
    if (current - windowStart >= WINDOW_MS) {
      windowStart = current;
      totalRequests = 0;
      totalMutations = 0;
      clients.clear();
    }
    const key = clientKey(request);
    let record = clients.get(key);
    if (!record || current - record.windowStart >= WINDOW_MS) {
      record = { windowStart: current, requests: 0, mutations: 0 };
      clients.set(key, record);
    }
    // Bound memory even if a proxy unexpectedly supplies many distinct IPs.
    if (clients.size > 512) {
      const oldest = clients.keys().next().value;
      if (oldest !== undefined && oldest !== key) clients.delete(oldest);
    }

    if (
      totalRequests >= MAX_TOTAL_REQUESTS ||
      (mutation && totalMutations >= MAX_TOTAL_MUTATIONS) ||
      record.requests >= MAX_CLIENT_REQUESTS ||
      (mutation && record.mutations >= MAX_CLIENT_MUTATIONS)
    ) {
      return false;
    }
    totalRequests += 1;
    record.requests += 1;
    if (mutation) {
      totalMutations += 1;
      record.mutations += 1;
    }
    return true;
  }

  return async function proxyJudgeDemoRequest(request) {
    const incoming = new URL(request.url);
    if (!incoming.pathname.startsWith("/api/") || incoming.search) {
      return jsonResponse(404, "Demo API route not found");
    }
    if (request.method !== "GET" && request.method !== "POST") {
      return jsonResponse(405, "Method not allowed");
    }

    const apiPath = incoming.pathname.slice("/api".length);
    if (!ALLOWED_ROUTES.some(([method, pattern]) => method === request.method && pattern.test(apiPath))) {
      return jsonResponse(404, "Demo API route not found");
    }
    const mutation = request.method === "POST";
    if (!admit(request, mutation)) {
      return jsonResponse(429, "Demo request limit reached; retry in a minute");
    }

    const backendValue = env.AXIOM_BACKEND_INTERNAL_URL;
    if (!backendValue) {
      return jsonResponse(503, "Demo backend is not configured");
    }
    let backend;
    try {
      backend = new URL(backendValue);
    } catch {
      return jsonResponse(503, "Demo backend configuration is invalid");
    }
    if (backend.protocol !== "http:" || !backend.hostname.endsWith(".railway.internal")) {
      return jsonResponse(503, "Demo backend must use a private Railway service address");
    }

    let body;
    const headers = { accept: "application/json", "x-axiom-client-ip": clientKey(request) };
    if (mutation) {
      const contentType = request.headers.get("content-type") || "";
      if (!contentType.toLowerCase().startsWith("application/json")) {
        return jsonResponse(415, "Demo API accepts JSON requests only");
      }
      try {
        body = await readBoundedBody(request);
      } catch {
        return jsonResponse(400, "Could not read demo request");
      }
      if (body === null) return jsonResponse(413, "Demo request body is too large");
      headers["content-type"] = "application/json";
    }

    const target = new URL(apiPath, backend);
    const targetUrl = target.toString();
    let upstream;
    try {
      upstream = await fetchImpl(targetUrl, {
        method: request.method,
        headers,
        ...(mutation ? { body } : {}),
        cache: "no-store",
        redirect: "error",
        signal: AbortSignal.timeout(5_000),
      });
    } catch {
      return jsonResponse(502, "Demo backend request failed");
    }

    let responseBody;
    try {
      responseBody = await upstream.arrayBuffer();
    } catch {
      return jsonResponse(502, "Demo backend response could not be read");
    }
    if (responseBody.byteLength > MAX_RESPONSE_BYTES) {
      return jsonResponse(502, "Demo backend response exceeded the size limit");
    }
    const contentType = upstream.headers.get("content-type");
    return new Response(responseBody, {
      status: upstream.status,
      headers: {
        "content-type": contentType?.startsWith("application/json")
          ? contentType
          : "application/json; charset=utf-8",
        "cache-control": "no-store",
        "x-content-type-options": "nosniff",
      },
    });
  };
}
