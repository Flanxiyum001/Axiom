import test from "node:test";
import assert from "node:assert/strict";

test("live showcase is isolated from the public backend proxy", async () => {
  const proxy = await import("./judge-demo-proxy.mjs");
  let calls = 0;
  const handler = proxy.createJudgeDemoProxy({
    env: { AXIOM_BACKEND_INTERNAL_URL: "http://axiom-backend.railway.internal:8000" },
    fetchImpl: async () => { calls += 1; return Response.json({}); },
  });
  const response = await handler(new Request("https://axiom.example/api/showcase/nemotron", { method: "POST" }));
  assert.equal(response.status, 404);
  assert.equal(calls, 0);
});
