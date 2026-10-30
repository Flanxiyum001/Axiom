import test from "node:test";
import assert from "node:assert/strict";

import { createJudgeDemoProxy } from "./judge-demo-proxy.mjs";

const backend = "http://axiom-backend.railway.internal:8000";

function request(path, options = {}) {
  return new Request("https://axiom-demo.example" + path, options);
}

test("proxies allowed health request to the private Railway backend without caching", async () => {
  const calls = [];
  const proxy = createJudgeDemoProxy({
    env: { AXIOM_BACKEND_INTERNAL_URL: backend },
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return Response.json({
        status: "ok",
        provider: "echo",
        demo_mode: true,
        workload: "fixed_synthetic_cpu",
      });
    },
  });

  const response = await proxy(request("/api/health", {
    headers: { "x-forwarded-for": "203.0.113.8" },
  }));
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.deepEqual(await response.json(), {
    status: "ok",
    provider: "echo",
    demo_mode: true,
    workload: "fixed_synthetic_cpu",
  });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, backend + "/health");
  assert.equal(calls[0].options.method, "GET");
  assert.equal(calls[0].options.redirect, "error");
  assert.equal(calls[0].options.headers["x-axiom-client-ip"], "203.0.113.8");
});

test("does not expose unsupported backend routes such as one-shot research", async () => {
  let called = false;
  const proxy = createJudgeDemoProxy({
    env: { AXIOM_BACKEND_INTERNAL_URL: backend },
    fetchImpl: async () => {
      called = true;
      return Response.json({});
    },
  });

  const response = await proxy(request("/api/research", { method: "GET" }));
  assert.equal(response.status, 404);
  assert.equal(called, false);
});

test("rejects oversized POST bodies before calling the backend", async () => {
  let called = false;
  const proxy = createJudgeDemoProxy({
    env: { AXIOM_BACKEND_INTERNAL_URL: backend },
    fetchImpl: async () => {
      called = true;
      return Response.json({});
    },
  });

  const response = await proxy(request("/api/objectives", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "content-length": "2049",
    },
    body: "x".repeat(2049),
  }));
  assert.equal(response.status, 413);
  assert.equal(called, false);
});

test("refuses a public or non-Railway backend destination", async () => {
  let called = false;
  const proxy = createJudgeDemoProxy({
    env: { AXIOM_BACKEND_INTERNAL_URL: "https://example.com" },
    fetchImpl: async () => {
      called = true;
      return Response.json({});
    },
  });

  const response = await proxy(request("/api/health"));
  assert.equal(response.status, 503);
  assert.equal(called, false);
});

test("enforces the per-client mutation limit", async () => {
  let called = 0;
  const proxy = createJudgeDemoProxy({
    env: { AXIOM_BACKEND_INTERNAL_URL: backend },
    fetchImpl: async () => {
      called += 1;
      return Response.json({ objective: { id: "obj_demo" } }, { status: 201 });
    },
  });

  for (let i = 0; i < 30; i += 1) {
    const response = await proxy(request("/api/objectives", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-forwarded-for": "203.0.113.8",
      },
      body: JSON.stringify({ description: "Reduce model inference latency by 20%" }),
    }));
    if (i < 6) assert.equal(response.status, 201);
    else assert.equal(response.status, 429);
  }
  assert.equal(called, 6);
});

test("returns a sanitized gateway error if the private backend is unavailable", async () => {
  const proxy = createJudgeDemoProxy({
    env: { AXIOM_BACKEND_INTERNAL_URL: backend },
    fetchImpl: async () => {
      throw new Error("private host details and secret value must not escape");
    },
  });

  const response = await proxy(request("/api/health"));
  assert.equal(response.status, 502);
  assert.deepEqual(await response.json(), { detail: "Demo backend request failed" });
});
