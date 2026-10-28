import { test, expect } from "@playwright/test";

test("dashboard runs an offline objective and restores provenance from API history", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  // The browser smoke test is local-only, including any assets it requests.
  await page.route("**/*", (route) => {
    const url = new URL(route.request().url());
    return ["127.0.0.1", "localhost"].includes(url.hostname) ? route.continue() : route.abort();
  });
  await page.goto("/");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  if (process.env.AXIOM_CAPTURE_VISUALS === "1") {
    await page.screenshot({ path: "test-results/axiom-hero-desktop.png", animations: "disabled" });
  }
  await expect(page.locator(".provider-line")).toHaveText("echo");
  await page.getByLabel("What should AXIOM investigate?").fill("Reduce model inference latency by 20%");
  await page.getByRole("button", { name: "Create objective" }).click();
  await expect(page.getByRole("button", { name: "Run research" })).toBeEnabled();

  const responsePromise = page.waitForResponse((response) =>
    response.url().endsWith("/run") && response.request().method() === "POST",
    { timeout: 75_000 });
  await page.getByRole("button", { name: "Run research" }).click();
  const response = await responsePromise;
  expect(response.ok(), await response.text()).toBeTruthy();
  const { summary } = await response.json();
  expect(summary.evaluation).toBeTruthy();
  expect(summary.evidence).toBeTruthy();
  expect(summary.spec.workload_type).toBe("synthetic");
  expect(summary.lever).toBe("batch_size");
  if (summary.evaluation.target_met) {
    const resultHeading = page.locator(".results-stack > .result-heading");
    await expect(resultHeading.getByRole("heading", { name: "Script metric target reached" })).toBeVisible();
    await expect(resultHeading.locator(".pill")).toHaveText("Synthetic script metric target met");
  }
  await expect(page.locator(".hypothesis-statement")).toHaveText(summary.hypothesis.statement);
  await expect(page.getByRole("heading", { name: "Baseline vs candidate" })).toBeVisible();
  await expect(page.locator(".evidence-card")).toContainText(summary.evidence.conclusion);
  const provenance = page.getByTestId("benchmark-provenance");
  await expect(provenance).toContainText("Synthetic workload; not real model inference");
  await expect(provenance).toContainText("batch size");
  await expect(provenance).toContainText(JSON.stringify(Object.fromEntries(
    summary.plan.variables.map((v) => [v.name, v.baseline_value]))));
  await expect(provenance).toContainText(JSON.stringify(Object.fromEntries(
    summary.plan.variables.map((v) => [v.name, v.candidate_value]))));
  await expect(provenance).toContainText(JSON.stringify(summary.spec.environment));

  await page.reload();
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await expect(page.locator(".hypothesis-statement")).toHaveText(summary.hypothesis.statement);
  await expect(provenance).toContainText("Synthetic workload; not real model inference");
  await expect(page.locator(".evidence-card")).toContainText(summary.evidence.conclusion);
  await expect(page.getByText("1 recorded experiment iteration", { exact: true })).toBeVisible();
  if (process.env.AXIOM_CAPTURE_VISUALS === "1") {
    await page.locator(".workspace-grid").screenshot({ path: "test-results/axiom-evidence-desktop.png", animations: "disabled" });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: "test-results/axiom-evidence-mobile.png", fullPage: true, animations: "disabled" });
  }
  expect(errors).toEqual([]);
});

for (const [interventionStatus, statusText] of [
  ["insufficient", "Insufficient evidence for optimization"],
  ["mismatch", "Intervention mismatch"],
]) {
  test(`a met script threshold does not prove an intervention with ${interventionStatus} status`, async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("API connected", { exact: true })).toBeVisible();
    const created = page.waitForResponse((response) =>
      response.url().endsWith("/objectives") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Create objective" }).click();
    const { objective } = await (await created).json();

    await page.route("**/objectives/*/run", (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ summary: {
        objective,
        hypothesis: { statement: "Optimize threads", rationale: "proposed treatment" },
        plan: { variables: [{ name: "threads", baseline_value: "1", candidate_value: "4" }] },
        spec: {
          workload_type: "synthetic",
          intervention_status: interventionStatus,
          intervention_detail: "Executed intervention has not been verified",
          code: 'LEVER = "threads"',
        },
        evaluation: {
          target_met: true,
          improvement_percent: 25,
          baseline_metrics: { latency_ms: 100 },
          candidate_metrics: { latency_ms: 75 },
          deltas: { latency_ms: -25 },
        },
        evidence: {
          hypothesis_supported: false,
          confidence: 0,
          conclusion: "Insufficient evidence to support the proposed optimization",
        },
        target_met: true,
        stopped: true,
        stop_reason: "target_met",
      } }),
    }));
    await page.getByRole("button", { name: "Run research" }).click();

    const resultHeading = page.locator(".results-stack > .result-heading");
    await expect(resultHeading.getByRole("heading", { name: "Script metric target reached" })).toBeVisible();
    await expect(resultHeading.locator(".pill")).toHaveText(statusText);
    await expect(resultHeading.locator(".pill")).toHaveClass(/pill-neutral/);
    await expect(resultHeading).not.toContainText("Measured target reached");
    await expect(resultHeading.locator(".pill")).not.toHaveText("Target met");
    await expect(page.locator(".evidence-card")).toContainText("Insufficient evidence");
    await expect(page.getByTestId("benchmark-provenance")).toContainText("Synthetic workload; not real model inference");
  });
}
