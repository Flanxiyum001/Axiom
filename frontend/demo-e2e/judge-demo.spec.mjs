import { test, expect } from "@playwright/test";

test("fixed judge demo shows measured synthetic evidence and blocks one-shot research", async ({ page, request }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/*", (route) => {
    const url = new URL(route.request().url());
    return ["127.0.0.1", "localhost"].includes(url.hostname) ? route.continue() : route.abort();
  });

  await page.goto("/");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await expect(page.getByTestId("demo-banner")).toContainText("Fixed synthetic CPU demo");
  await expect(page.locator(".provider-line")).toHaveText("echo");
  await expect(page.getByLabel("What should AXIOM investigate?")).toHaveAttribute("readonly", "");
  await expect(page.locator("#api-url")).toHaveCount(0);

  await page.getByRole("button", { name: "Create objective" }).click();
  await expect(page.locator("#iteration-count option")).toHaveCount(1);
  const responsePromise = page.waitForResponse((response) =>
    response.url().endsWith("/run") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Run research" }).click();
  const response = await responsePromise;
  expect(response.ok(), await response.text()).toBeTruthy();
  const { summary } = await response.json();
  expect(summary.spec.workload_type).toBe("synthetic");
  expect(summary.spec.code).toContain("never executed");
  expect(summary.evaluation.baseline_metrics.latency_ms).toBeGreaterThan(0);
  expect(summary.evaluation.candidate_metrics.latency_ms).toBeGreaterThan(0);
  await expect(page.getByRole("heading", { name: "Baseline vs candidate" })).toBeVisible();
  await expect(page.getByTestId("benchmark-provenance")).toContainText("no model inference");
  await expect(page.locator(".evidence-card")).toContainText("synthetic CPU task");

  await page.reload();
  await expect(page.getByText("1 recorded experiment iteration", { exact: true })).toBeVisible();
  await expect(page.getByTestId("demo-banner")).toBeVisible();
  const blocked = await request.post("http://127.0.0.1:8101/research", {
    data: { description: "Reduce model inference latency by 20%" },
  });
  expect(blocked.status()).toBe(403);
  expect(errors).toEqual([]);
});
