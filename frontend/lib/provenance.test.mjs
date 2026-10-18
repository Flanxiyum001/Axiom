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

test("derives history provenance for precision when no summary lever exists", () => {
  const value = deriveProvenance({
    hypothesis: { statement: "Use FP16 precision" },
    plan: { variables: [{ name: "precision", baseline_value: "fp32", candidate_value: "fp16" }] },
    spec: { workload_type: "synthetic", code: 'LEVER = "precision"\\n' },
    runs: [{ id: "a" }, { id: "b" }],
  });
  assert.equal(value.lever, "precision");
  assert.equal(value.leverConsistency, "consistent");
  assert.equal(value.runCount, 2);
  assert.deepEqual(value.baselineSettings, { precision: "fp32" });
  assert.deepEqual(value.candidateSettings, { precision: "fp16" });
});

test("reports a mismatch across available provenance sources", () => {
  const value = deriveProvenance({
    lever: "threads",
    hypothesis: { statement: "Set CPU threads to four" },
    plan: { variables: [{ name: "precision", baseline_value: "fp32", candidate_value: "fp16" }] },
    spec: { workload_type: "synthetic", code: 'LEVER = "precision"\\n' },
    run_ids: [],
  });
  assert.equal(value.lever, "precision");
  assert.equal(value.leverConsistency, "mismatch");
});

test("does not invent a lever or workload when provenance is absent", () => {
  const value = deriveProvenance({});
  assert.equal(value.lever, "unknown");
  assert.equal(value.workloadType, "unknown");
  assert.equal(value.leverConsistency, "insufficient");
  assert.equal(value.measurementMethod, "Workload type not recorded");
  assert.deepEqual(value.baselineSettings, {});
  assert.deepEqual(value.candidateSettings, {});
});

test("uses explicit synthetic-workload wording", () => {
  const value = deriveProvenance({ workload_type: "synthetic", spec: { workload_type: "synthetic" } });
  assert.equal(value.measurementMethod, "Synthetic workload; not real model inference");
});

test("derives provenance from the fresh loop-summary API shape", () => {
  const value = deriveProvenance({
    workload_type: "synthetic",
    lever: "threads",
    hypothesis: { statement: "Set CPU threads to four" },
    plan: { variables: [{ name: "cpu_threads", baseline_value: "1", candidate_value: "4" }] },
    spec: {
      workload_type: "synthetic",
      code: 'LEVER = "threads"',
      parameters: { sample_count: 3 },
      environment: { EXPERIMENT_MODE: "candidate" },
    },
    run_ids: ["1", "2", "3"],
  });
  assert.equal(value.lever, "threads");
  assert.equal(value.leverConsistency, "consistent");
  assert.equal(value.runCount, 3);
  assert.deepEqual(value.baselineSettings, { cpu_threads: "1" });
  assert.deepEqual(value.candidateSettings, { cpu_threads: "4" });
  assert.deepEqual(value.environment, { EXPERIMENT_MODE: "candidate" });
  assert.deepEqual(value.parameters, { sample_count: 3 });
});

