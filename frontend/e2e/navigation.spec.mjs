import { test, expect } from "@playwright/test";

test("AXIOM shares navigation and branding across the research and assistant routes", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));

  // Backward-compatible entry route, including the existing workspace anchor.
  await page.goto("/#objective-workspace");
  await expect(page.locator("#objective-workspace")).toBeVisible();
  const navigation = page.getByRole("navigation", { name: "AXIOM capabilities" });
  await expect(navigation.getByRole("link", { name: "Research Workspace" })).toHaveAttribute("aria-current", "page");
  await expect(navigation.getByRole("link", { name: "AI Research Assistant" })).toHaveAttribute("href", "/showcase");
  await expect(page.getByRole("link", { name: "AXIOM home" })).toHaveAttribute("href", "/#objective-workspace");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();

  await navigation.getByRole("link", { name: "AI Research Assistant" }).click();
  await expect(page).toHaveURL(/\/showcase$/);
  await expect(navigation.getByRole("link", { name: "AI Research Assistant" })).toHaveAttribute("aria-current", "page");
  await expect(page.locator(".showcase-lede")).toContainText("NVIDIA Nemotron 3 Super");
  await expect(page.locator(".showcase-lede")).toContainText("Nebius Token Factory");
  await expect(page.locator(".showcase-lede")).toContainText("not experiment execution");
  await expect(page.getByRole("button", { name: "Generate live experiment proposal" })).toBeEnabled();
  await expect(page.getByText("Proposal generation only", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Research lab", exact: true }).click();
  await expect(page).toHaveURL(/\/#objective-workspace$/);
  await expect(page.getByRole("heading", { name: /Experiment workspace/ })).toBeVisible();
  await expect(navigation.getByRole("link", { name: "Research Workspace" })).toHaveAttribute("aria-current", "page");
  expect(errors).toEqual([]);
});

test("mobile navigation stays accessible with shared dark/light theme and no horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/showcase");
  const navigation = page.getByRole("navigation", { name: "AXIOM capabilities" });
  await expect(navigation.getByRole("link", { name: "AI Research Assistant" })).toBeVisible();
  await expect(navigation.getByRole("link", { name: "AI Research Assistant" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("link", { name: "AXIOM home" })).toBeVisible();
  const switchControl = page.getByRole("switch", { name: "Dark mode" });
  await expect(switchControl).toHaveAttribute("aria-checked", "true");
  const horizontalOverflow = () => page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth + 1
  );
  expect(await horizontalOverflow()).toBe(false);

  await switchControl.click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await navigation.getByRole("link", { name: "Research Workspace" }).click();
  await expect(page).toHaveURL(/\/#objective-workspace$/);
  await expect(navigation.getByRole("link", { name: "Research Workspace" })).toHaveAttribute("aria-current", "page");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  expect(await horizontalOverflow()).toBe(false);
  await navigation.getByRole("link", { name: "AI Research Assistant" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  expect(await horizontalOverflow()).toBe(false);
});
