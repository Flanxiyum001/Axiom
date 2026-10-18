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
  expect(errors).toEqual([]);
});
