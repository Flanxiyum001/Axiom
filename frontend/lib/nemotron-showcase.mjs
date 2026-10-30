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
  "Include exactly the five required JSON string fields. Keep each field concise, nonempty, and below 1200 characters.",
].join("\n");

// Modern browsers send Fetch Metadata. Refuse cross-site browser-triggered
// POSTs so a third-party page cannot casually consume the showcase's quota.
// This is defense in depth, not authentication or global provider rate limiting.
export function isCrossSiteShowcaseRequest(headers) {
  return headers?.get?.("sec-fetch-site")?.toLowerCase() === "cross-site";
}

export function verifyNemotronModel(model) {
  if (model !== MODEL) {
    throw new Error("Nebius returned an unexpected or missing model identifier.");
  }
  return model;
}

// Diagnostics contain only JSON structure, types and lengths: never the
// provider's generated text, reasoning trace, or credential-bearing headers.
// The bounded key labels exclude arbitrary strings and control characters.
export function inspectNemotronContent(content) {
  const contentType = content === null ? "null" : Array.isArray(content) ? "array" : typeof content;
  const base = { contentType, parsedKeys: [], keyCount: 0, fields: {}, condition: "valid", failedField: null };
  if (typeof content !== "string") return { ...base, condition: "content_not_string" };
  let parsed;
  try {
    parsed = JSON.parse(content);
  } catch {
    return { ...base, condition: "invalid_json" };
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    return { ...base, condition: "invalid_json_root" };
  }
  const keys = Object.keys(parsed);
  const safeKey = (key) => /^[a-z][a-z0-9_]{0,39}$/.test(key) ? key : "<invalid-key>";
  base.parsedKeys = keys.slice(0, 20).map(safeKey);
  base.keyCount = keys.length;
  for (const field of REQUIRED_FIELDS) {
    const present = Object.hasOwn(parsed, field);
    const value = present ? parsed[field] : undefined;
    const type = !present ? "missing" : value === null ? "null" : Array.isArray(value) ? "array" : typeof value;
    const characterCount = typeof value === "string" ? Array.from(value).length : null;
    const utf16Length = typeof value === "string" ? value.length : null;
    let condition = "valid";
    if (!present) condition = "missing_field";
    else if (type !== "string") condition = "non_string_field";
    else if (!value.trim()) condition = "empty_field";
    else if (utf16Length > 1200) condition = "oversized_field";
    base.fields[field] = { type, characterCount, utf16Length, condition };
    if (base.condition === "valid" && condition !== "valid") {
      base.condition = condition;
      base.failedField = field;
    }
  }
  if (base.condition === "valid" && keys.some((key) => !REQUIRED_FIELDS.includes(key))) {
    base.condition = "unexpected_keys";
  }
  return base;
}

export class NemotronContentError extends Error {
  constructor(condition, field) {
    super(condition === "invalid_json" ? "Nemotron response was not valid JSON." :
      "Nemotron response did not pass output validation.");
    this.name = "NemotronContentError";
    this.condition = condition;
    this.field = field ?? null;
  }
}

export function parseNemotronContent(content) {
  const diagnostics = inspectNemotronContent(content);
  if (diagnostics.condition !== "valid") {
    throw new NemotronContentError(diagnostics.condition, diagnostics.failedField);
  }
  const parsed = JSON.parse(content);
  return Object.fromEntries(REQUIRED_FIELDS.map((field) => [field, parsed[field].trim()]));
}

// A small, allowlisted, redacted log record. No raw completion text, no
// provider error body, no Authorization header or secret environment fields.
export function describeNemotronResponse({ upstreamStatus = null, responseContentType = null, payload = null, condition = null } = {}) {
  const rawModel = payload?.model;
  const rawFinish = payload?.choices?.[0]?.finish_reason;
  const rawMime = typeof responseContentType === "string" ? responseContentType.split(";")[0].trim().toLowerCase() : "";
  const mime = /^[a-z0-9.+-]{1,35}\/[a-z0-9.+-]{1,35}$/.test(rawMime) ? rawMime : "unknown";
  const model = typeof rawModel === "string" && /^[a-zA-Z0-9/_.-]{1,128}$/.test(rawModel)
    ? rawModel : "unknown_or_invalid";
  const finishReason = typeof rawFinish === "string" && /^(stop|length|content_filter|tool_calls|function_call)$/.test(rawFinish)
    ? rawFinish : "missing_or_unrecognized";
  const content = inspectNemotronContent(payload?.choices?.[0]?.message?.content);
  return {
    event: "axiom.nemotron.response_diagnostic",
    upstreamHttpStatus: Number.isInteger(upstreamStatus) && upstreamStatus >= 100 && upstreamStatus <= 599 ? upstreamStatus : null,
    returnedModel: model,
    modelMatchesExpected: rawModel === MODEL,
    finishReason,
    responseContentType: mime,
    messageContentType: content.contentType,
    parsedJsonKeys: content.parsedKeys,
    parsedJsonKeyCount: content.keyCount,
    requiredFields: content.fields,
    failureCondition: condition || content.condition,
    failedField: content.failedField,
  };
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
    // Nemotron 3 Super reasons by default; use a final-answer budget for this
    // short JSON-only showcase rather than spending it on hidden reasoning.
    max_tokens: 1024,
    chat_template_kwargs: { enable_thinking: false },
    stream: false,
    response_format: {
      type: "json_schema",
      json_schema: { name: "axiom_showcase", strict: true, schema: RESPONSE_SCHEMA },
    },
  };
}
