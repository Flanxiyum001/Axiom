import { test, expect } from "@playwright/test";

const validOutput = {
  hypothesis: "A shorter sequence may reduce latency.",
  experiment: "Compare a fixed baseline against a shorter-sequence candidate.",
  metric: "Median response latency.",
  safety_check: "Generated code is not executed by this showcase.",
  limitation: "This is a proposal, not a measured benchmark.",
};

test("live showcase is readable and renders a clearly bounded mocked proposal", async ({ page }) => {
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  // No paid provider request in the browser regression.
  await page.route("**/api/showcase/nemotron", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      provider: "Nebius Token Factory",
      model: "nvidia/nemotron-3-super-120b-a12b",
      result: validOutput,
      evidence_status: "model-generated proposal; no experiment executed",
      generated_at: "2026-10-28T12:00:00Z",
      cached: false,
    }),
  }));
  await page.goto("/");
  const showcaseLink = page.getByRole("link", { name: /live Nemotron reasoning/ });
  await expect(showcaseLink).toHaveAttribute("href", "/showcase");
  await showcaseLink.click();
  await expect(page.getByRole("heading", { name: /Reasoning,.*Evidence,.*honest\./ })).toBeVisible();
  await expect(page.getByRole("link", { name: "Research lab", exact: true })).toHaveAttribute("href", "/#objective-workspace");
  const heroColor = await page.locator(".showcase-hero").evaluate((element) => getComputedStyle(element).backgroundColor);
  expect(heroColor).toBe("rgb(16, 32, 35)");
  await page.getByRole("button", { name: "Generate live experiment proposal" }).click();
  await expect(page.getByText(validOutput.hypothesis)).toBeVisible();
  await expect(page.getByTestId("showcase-evidence")).toContainText("no experiment executed");
  await expect(page.getByText("live LLM-generated proposal")).toBeVisible();
  expect(pageErrors).toEqual([]);
});

test("showcase gives a useful error on provider cooldown without inventing a result", async ({ page }) => {
  await page.route("**/api/showcase/nemotron", (route) => route.fulfill({
    status: 429, contentType: "application/json",
    body: JSON.stringify({ error: "Please wait before requesting another model response." }),
  }));
  await page.goto("/showcase");
  await page.getByRole("button", { name: "Generate live experiment proposal" }).click();
  await expect(page.locator(".showcase-error[role=alert]")).toContainText("Please wait");
  await expect(page.getByText("No model proposal requested yet")).toBeVisible();
  await expect(page.getByRole("button", { name: "Generate live experiment proposal" })).toBeEnabled();
});


test("malformed Nemotron output fails closed without fabricating a proposal", async ({ page }) => {
  await page.route("**/api/showcase/nemotron", (route) => route.fulfill({
    status: 502, contentType: "application/json",
    body: JSON.stringify({ error: "Nemotron response did not pass output validation." }),
  }));
  await page.goto("/showcase");
  await page.getByRole("button", { name: "Generate live experiment proposal" }).click();
  await expect(page.locator(".showcase-error[role=alert]")).toContainText("output validation");
  await expect(page.getByText("No model proposal requested yet")).toBeVisible();
  await expect(page.locator(".showcase-output")).toHaveCount(0);
});
