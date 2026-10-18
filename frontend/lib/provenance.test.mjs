import assert from "node:assert/strict";
import test from "node:test";
import { deriveProvenance } from "./provenance.mjs";

test("history provenance", () => {
  const value = deriveProvenance({
    hypothesis: { statement: "Optimize threads" },
    plan: { variables: [{ name: "threads", baseline_value: "1", candidate_value: "4" }] },
    spec: { workload_type: "synthetic", code: 'LEVER = "threads"\n' },
    runs: [{ id: "a" }],
  });
  assert.equal(value.lever, "threads");
  assert.equal(value.leverConsistency, "consistent");
  assert.equal(value.runCount, 1);
});