import test from "node:test";
import assert from "node:assert/strict";

import {
  BASE_URL,
  FIXED_PROMPT,
  MODEL,
  buildNemotronRequest,
  parseNemotronContent,
  inspectNemotronContent,
  describeNemotronResponse,
  validateNemotronCompletion,
  NemotronContentError,
  verifyNemotronModel,
  isCrossSiteShowcaseRequest,
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
  assert.equal(request.max_tokens, 1024);
  assert.deepEqual(request.chat_template_kwargs, { enable_thinking: false });
  assert.equal(request.stream, false);
  assert.equal(request.response_format.type, "json_schema");
  assert.equal(request.response_format.json_schema.strict, true);
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

test("rejects missing or mismatched response model attribution", () => {
  assert.equal(verifyNemotronModel(MODEL), MODEL);
  assert.throws(() => verifyNemotronModel(undefined), /unexpected or missing model/);
  assert.throws(() => verifyNemotronModel("some-other-model"), /unexpected or missing model/);
});

test("rejects cross-site browser request metadata without blocking same-origin calls", () => {
  assert.equal(isCrossSiteShowcaseRequest(new Headers({ "sec-fetch-site": "cross-site" })), true);
  assert.equal(isCrossSiteShowcaseRequest(new Headers({ "sec-fetch-site": "same-origin" })), false);
  assert.equal(isCrossSiteShowcaseRequest(new Headers({ "sec-fetch-site": "none" })), false);
  assert.equal(isCrossSiteShowcaseRequest(new Headers()), false);
});


test("diagnoses the exact missing field without recording its content", () => {
  const content = JSON.stringify({ ...valid, safety_check: "" });
  const diagnostics = inspectNemotronContent(content);
  assert.equal(diagnostics.condition, "empty_field");
  assert.equal(diagnostics.failedField, "safety_check");
  assert.equal(diagnostics.fields.safety_check.type, "string");
  assert.equal(diagnostics.fields.safety_check.characterCount, 0);
  assert.deepEqual(diagnostics.parsedKeys, Object.keys(valid));
  assert.throws(() => parseNemotronContent(content),
    (err) => err instanceof NemotronContentError && err.condition === "empty_field"
      && err.field === "safety_check");
});

test("diagnoses missing, null, array, numeric and oversized structured fields", () => {
  const cases = [
    [{ ...valid, hypothesis: null }, "non_string_field", "hypothesis", "null"],
    [{ ...valid, experiment: ["do not run"] }, "non_string_field", "experiment", "array"],
    [{ ...valid, metric: 0 }, "non_string_field", "metric", "number"],
    [{ ...valid, limitation: "x".repeat(1201) }, "oversized_field", "limitation", "string"],
    [Object.fromEntries(Object.entries(valid).filter(([k]) => k !== "limitation")), "missing_field", "limitation", "missing"],
  ];
  for (const [payload, condition, field, type] of cases) {
    const content = JSON.stringify(payload);
    const details = inspectNemotronContent(content);
    assert.equal(details.condition, condition);
    assert.equal(details.failedField, field);
    assert.equal(details.fields[field].type, type);
    assert.throws(() => parseNemotronContent(content), /output validation/);
  }
});

test("fails closed on unexpected keys, malformed JSON and non-object responses", () => {
  for (const [content, reason] of [
    ['{"hypothesis":"unfinished",', "invalid_json"],
    ['[]', "invalid_json_root"],
    ['null', "invalid_json_root"],
    ['"a text answer"', "invalid_json_root"],
    [null, "content_not_string"],
    [JSON.stringify({ ...valid, extra: "not in schema" }), "unexpected_keys"],
  ]) {
    assert.equal(inspectNemotronContent(content).condition, reason);
    assert.throws(() => parseNemotronContent(content));
  }
  assert.equal(inspectNemotronContent(JSON.stringify(valid)).condition, "valid");
});

test("redacted diagnostics include HTTP, model, finish reason, MIME, JSON keys and field sizes", () => {
  const payload = {
    model: MODEL,
    choices: [{ finish_reason: "length", message: {
      content: JSON.stringify({
        ...valid,
        limitation: "secret sensitive proposal content",
      }),
    } }],
  };
  const diag = describeNemotronResponse({
    upstreamStatus: 200,
    responseContentType: "application/json; charset=utf-8",
    payload,
    condition: "output_truncated",
  });
  assert.equal(diag.upstreamHttpStatus, 200);
  assert.equal(diag.returnedModel, MODEL);
  assert.equal(diag.modelMatchesExpected, true);
  assert.equal(diag.finishReason, "length");
  assert.equal(diag.responseContentType, "application/json");
  assert.equal(diag.messageContentType, "string");
  assert.deepEqual(diag.parsedJsonKeys, Object.keys(valid));
  assert.equal(diag.requiredFields.limitation.characterCount, "secret sensitive proposal content".length);
  assert.equal(diag.failureCondition, "output_truncated");
  const serialized = JSON.stringify(diag);
  assert.doesNotMatch(serialized, /secret sensitive proposal content|Authorization|Bearer|NEBIUS_API_KEY/);
});

test("invalid model identities and untrusted JSON key names are safely redacted", () => {
  const secret = "Bearer should not be logged";
  const diag = describeNemotronResponse({
    upstreamStatus: 502,
    responseContentType: "application/json",
    payload: {
      model: secret,
      choices: [{ finish_reason: secret, message: { content: JSON.stringify({
        ...valid, [secret]: "hidden", hypothesis: secret,
      }) } }],
    },
    condition: "model_mismatch",
  });
  assert.equal(diag.returnedModel, "unknown_or_invalid");
  assert.equal(diag.modelMatchesExpected, false);
  assert.equal(diag.finishReason, "missing_or_unrecognized");
  assert.ok(diag.parsedJsonKeys.includes("<invalid-key>"));
  assert.equal(diag.failureCondition, "model_mismatch");
  assert.doesNotMatch(JSON.stringify(diag), /Bearer should not be logged/);
});


test("strict completion validation refuses the actual truncation and unfinished-output family", () => {
  const okay = { model: MODEL, choices: [{ finish_reason: "stop", message: { content: JSON.stringify(valid) } }] };
  assert.deepEqual(validateNemotronCompletion(okay), { model: MODEL, result: valid });
  for (const finishReason of ["length", "content_filter", "tool_calls", null, undefined]) {
    const response = { ...okay, choices: [{ ...okay.choices[0], finish_reason: finishReason }] };
    assert.throws(() => validateNemotronCompletion(response), (error) =>
      error instanceof NemotronContentError
      && error.condition === (finishReason === "length" ? "output_truncated" : "finish_reason_not_stop"));
  }
  assert.throws(() => validateNemotronCompletion({ ...okay, model: "another-model" }),
    /unexpected or missing model identifier/);
});
