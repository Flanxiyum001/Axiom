export const MODEL = "nvidia/nemotron-3-super-120b-a12b";
export const BASE_URL = "https://api.tokenfactory.nebius.com/v1/chat/completions";
export const REQUIRED_FIELDS = ["hypothesis", "experiment", "metric", "safety_check", "limitation"];

export const RESPONSE_SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    hypothesis: { type: "string" },
    experiment: { type: "string" },
    metric: { type: "string" },
    safety_check: { type: "string" },
    limitation: { type: "string" },
  },
  required: REQUIRED_FIELDS,
};

export const FIXED_PROMPT = [
  "You are AXIOM, an evidence-first ML experiment planning assistant.",
  "Given the fixed objective: Reduce model inference latency by 20%.",
  "Return a concise, technically sound proposal for one controlled experiment.",
  "Do not claim that any experiment has run or that any performance improvement was measured.",
  "Do not invent benchmark results. Explicitly distinguish a hypothesis from measured evidence.",
  "The safety_check must say generated code is not executed by this showcase.",
  "The limitation must state that this response is a plan, not a benchmark result.",
].join("\n");

export function verifyNemotronModel(model) {
  if (model !== MODEL) {
    throw new Error("Nebius returned an unexpected or missing model identifier.");
  }
  return model;
}

export function parseNemotronContent(content) {
  let parsed;
  try {
    parsed = JSON.parse(content);
  } catch {
    throw new Error("Nemotron response was not valid JSON.");
  }
  for (const field of REQUIRED_FIELDS) {
    if (typeof parsed?.[field] !== "string" || !parsed[field].trim() || parsed[field].length > 1200) {
      throw new Error("Nemotron response did not pass output validation.");
    }
  }
  return Object.fromEntries(REQUIRED_FIELDS.map((field) => [field, parsed[field].trim()]));
}

export function buildNemotronRequest() {
  return {
    model: MODEL,
    messages: [
      {
        role: "system",
        content: "Return only a valid JSON object matching the requested schema. Never claim unobserved measurements.",
      },
      { role: "user", content: FIXED_PROMPT },
    ],
    temperature: 0.1,
    max_tokens: 500,
    response_format: {
      type: "json_schema",
      json_schema: { name: "axiom_showcase", strict: true, schema: RESPONSE_SCHEMA },
    },
  };
}
