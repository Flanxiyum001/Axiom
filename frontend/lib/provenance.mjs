function canonicalLever(value) {
  const normalized = String(value ?? "")
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .trim();

  const found = [];
  if (/\bbatch(?:ing| size)?\b/.test(normalized)) found.push("batch_size");
  if (/\bthreads?\b/.test(normalized)) found.push("threads");
  if (/precision|fp16|fp32|int8|quantiz/.test(normalized)) found.push("precision");
  if (/\b(?:cpu )?work units\b/.test(normalized)) found.push("cpu_work_units");
  return found.length === 1 ? found[0] : null;
}

function asObjectForPlanVariables(variables, field) {
  if (!Array.isArray(variables)) return {};
  return Object.fromEntries(
    variables
      .filter((variable) => variable && typeof variable.name === "string" && variable.name.trim())
      .map((variable) => [
        variable.name,
        variable[field] === null || variable[field] === undefined || variable[field] === ""
          ? "Not specified"
          : variable[field],
      ])
  );
}

/**
 * Normalize provenance from either a fresh LoopSummary API response or a
 * persisted ResearchHistory record. Missing facts remain explicitly unknown;
 * the dashboard must not invent a lever or claim real-model measurements.
 */
export function deriveProvenance(selectedRun) {
  if (!selectedRun) return null;

  const spec = selectedRun.spec || null;
  const plan = selectedRun.plan || null;
  const variables = Array.isArray(plan?.variables) ? plan.variables : [];
  const hypothesisLever = canonicalLever(selectedRun.hypothesis?.statement);
  const planLevers = variables.map((variable) => canonicalLever(variable?.name)).filter(Boolean);
  const planLever = new Set(planLevers).size === 1 ? planLevers[0] : null;
  const declaredLever = canonicalLever(selectedRun.lever);

  const codeMatch =
    typeof spec?.code === "string"
      ? spec.code.match(/^\s*LEVER\s*=\s*["']([a-z_]+)["']/m)
      : null;
  const codeLever = canonicalLever(codeMatch?.[1]);

  const leverSources = [
    ["hypothesis", hypothesisLever],
    ["plan", planLever],
    ["generated code", codeLever],
    ["API summary", declaredLever],
  ].filter((entry) => entry[1]);

  const sourceValues = new Set(leverSources.map((entry) => entry[1]));
  planLevers.forEach((lever) => sourceValues.add(lever));
  const leverConsistency =
    sourceValues.size > 1
      ? "mismatch"
      : sourceValues.size === 1 && leverSources.length >= 2
        ? "consistent"
        : "insufficient";

  const workloadType = spec?.workload_type || selectedRun.workload_type || "unknown";
  const runCount = Array.isArray(selectedRun.runs)
    ? selectedRun.runs.length
    : Array.isArray(selectedRun.run_ids)
      ? selectedRun.run_ids.length
      : 0;

  let measurementMethod = "Workload type not recorded";
  if (workloadType === "synthetic") {
    measurementMethod = "Synthetic workload; not real model inference";
  } else if (workloadType === "real_model_inference") {
    measurementMethod = "Declared real model-inference workload; implementation not independently verified";
  } else if (workloadType !== "unknown") {
    measurementMethod = `${workloadType.replaceAll("_", " ")} workload`;
  }

  const inferredLever = planLever || hypothesisLever || codeLever || declaredLever;

  return {
    workloadType,
    lever: inferredLever || "unknown",
    leverConsistency,
    leverSources: Object.fromEntries(leverSources),
    baselineSettings: asObjectForPlanVariables(variables, "baseline_value"),
    candidateSettings: asObjectForPlanVariables(variables, "candidate_value"),
    parameters: spec?.parameters && typeof spec.parameters === "object" ? spec.parameters : {},
    environment: spec?.environment && typeof spec.environment === "object" ? spec.environment : {},
    runCount,
    measurementMethod,
    interventionStatus: spec?.intervention_status || "insufficient",
    interventionDetail: spec?.intervention_detail || "Executed intervention has not been verified",
  };
}
