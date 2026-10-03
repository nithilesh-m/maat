import { expect, test, type Page } from "@playwright/test";

async function open(page: Page, path: string) {
  await page.goto(path);
  await page.waitForSelector("body[data-hydrated]");
}

// The Next.js route announcer is also role="alert"; ignore it.
const alert = (page: Page) => page.locator('[role="alert"]:not(#__next-route-announcer__)');

async function login(page: Page, token: string) {
  await open(page, "/login");
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/runs$/);
}

test("home page presents the product and links to the console", async ({ page }) => {
  await open(page, "/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("evidence you can");
  await expect(page.getByRole("link", { name: "Sign in to the console" })).toBeVisible();
  await page.getByRole("link", { name: "Sign in to the console" }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test("theme and accent choices apply and persist", async ({ page }) => {
  await open(page, "/");
  await page.getByRole("button", { name: "Theme and colour" }).first().click();
  await page.getByRole("button", { name: "Dark" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.getByRole("button", { name: "Emerald accent" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-accent", "emerald");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-accent", "emerald");
  await expect(page.locator("html")).toHaveClass(/dark/);
});

test("viewer sees runs, scores and clause matrix", async ({ page }) => {
  await login(page, "viewer-token");
  await page.getByRole("link", { name: "demo-vulnerable", exact: true }).click();
  await expect(page.getByText("Coverage").first()).toBeVisible();
  await page.getByRole("link", { name: "Clauses" }).click();
  await expect(page.getByRole("cell", { name: "VG-SEC-01" }).first()).toBeVisible();
  await expect(page.locator("tbody span", { hasText: /^block$/ }).first()).toBeVisible();
});

test("invalid token is rejected; expired session returns to login (Review Focus #1)", async ({ page }) => {
  await open(page, "/login");
  await page.getByLabel("API token").fill("nope");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(alert(page)).toContainText("Invalid token");
  await login(page, "viewer-token");
  await page.evaluate(() => sessionStorage.setItem("maat.token", "revoked"));
  await open(page, "/runs");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByText("Your session expired")).toBeVisible();
});

test("paused run shows the approval panel, not an error (Review Focus #3)", async ({ page }) => {
  await login(page, "reviewer-token");
  await open(page, "/runs/demo-paused");
  await expect(page.getByText("Approval needed")).toBeVisible();
  await expect(page.getByRole("button", { name: "Accept suggested tier" })).toBeVisible();
});

test("reviewer resolves an abstained control and the bundle still verifies", async ({ page }) => {
  await login(page, "reviewer-token");
  await open(page, "/review");
  const item = page.getByRole("article", { name: /^Review / }).first();
  await item.locator("label", { hasText: "Not satisfied" }).click();
  await expect(item.getByLabel("Not satisfied")).toBeChecked();
  await item.getByLabel("Rationale").fill("No oversight documentation supplied");
  await item.getByRole("button", { name: "Record decision" }).click();
  await open(page, "/runs/demo-vulnerable/bundle");
  await expect(page.getByText("VALID", { exact: true })).toBeVisible();
});

test("remediation delta shows the improvement", async ({ page }) => {
  await login(page, "viewer-token");
  await open(page, "/runs/demo-vulnerable/remediation");
  await expect(page.getByLabel("improved").first()).toBeVisible();
});

test("only admins can apply mitigations", async ({ page }) => {
  await login(page, "reviewer-token");
  await open(page, "/runs/demo-vulnerable/remediation");
  await expect(page.getByRole("button", { name: "Apply in sandbox" })).toBeDisabled();
});

test("viewer cannot reveal sensitive artifacts", async ({ page }) => {
  await login(page, "viewer-token");
  await open(page, "/runs/demo-vulnerable/clauses");
  const first = page.locator('a[href*="/records/"]').first();
  await first.click();
  const reveal = page.getByRole("button", { name: /Reveal sensitive artifact/ });
  if (await reveal.count()) await expect(reveal.first()).toBeDisabled();
});

test("new audit validates the profile before submitting", async ({ page }) => {
  await login(page, "reviewer-token");
  await page.getByRole("link", { name: "New audit" }).first().click();
  await page.getByLabel("Profile YAML").fill("name: x\n");
  await expect(alert(page)).toContainText("Missing keys");
  await expect(page.getByRole("button", { name: "Start audit" })).toBeDisabled();
});

test("viewers do not get the new-audit action", async ({ page }) => {
  await login(page, "viewer-token");
  await expect(page.getByRole("link", { name: "New audit" })).toHaveCount(1); // sidebar link only
  await open(page, "/runs/new");
  await expect(page.getByText("cannot start audits")).toBeVisible();
});

test("compare two runs highlights the changed control", async ({ page }) => {
  await login(page, "viewer-token");
  await open(page, "/runs/compare?a=demo-vulnerable&b=demo-hardened");
  await expect(page.locator('tr[data-changed="true"]').first()).toBeVisible();
});
