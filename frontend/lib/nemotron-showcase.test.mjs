import test from "node:test";
import assert from "node:assert/strict";

import {
  BASE_URL,
  FIXED_PROMPT,
  MODEL,
  buildNemotronRequest,
  parseNemotronContent,
} from "./nemotron-showcase.mjs";

const valid = {
  hypothesis: "Reducing sequence length may lower latency.",
  experiment: "Compare fixed baseline and candidate requests.",
  metric: "Median latency in milliseconds.",
  safety_check: "Generated code is not executed by this showcase.",
  limitation: "This is a plan, not a benchmark result.",
};

test("pins the eligible model and fixed evidence-first prompt", () => {
  const request = buildNemotronRequest();
  assert.equal(MODEL, "nvidia/nemotron-3-super-120b-a12b");
  assert.equal(BASE_URL, "https://api.tokenfactory.nebius.com/v1/chat/completions");
  assert.equal(request.model, MODEL);
  assert.equal(request.max_tokens, 500);
  assert.match(FIXED_PROMPT, /Do not invent benchmark results/);
  assert.match(FIXED_PROMPT, /not a benchmark result/);
  assert.equal(request.messages[1].content, FIXED_PROMPT);
});

test("accepts and trims all required structured fields", () => {
  const parsed = parseNemotronContent(JSON.stringify(Object.fromEntries(
    Object.entries(valid).map(([key, value]) => [key, "  " + value + "  "])
  )));
  assert.deepEqual(parsed, valid);
});

test("rejects invalid JSON", () => {
  assert.throws(() => parseNemotronContent("not json"), /not valid JSON/);
});

test("rejects missing or blank required fields", () => {
  assert.throws(() => parseNemotronContent(JSON.stringify({ ...valid, metric: " " })), /output validation/);
  const { limitation, ...missing } = valid;
  assert.throws(() => parseNemotronContent(JSON.stringify(missing)), /output validation/);
});

test("rejects oversized field content", () => {
  assert.throws(() => parseNemotronContent(JSON.stringify({ ...valid, hypothesis: "x".repeat(1201) })), /output validation/);
});
