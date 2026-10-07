// AC-1, AC-18: the walking-skeleton journey in a real browser (TASK-012 interface contract).
// Needs `make dev` running and `make seed` done. Sign in through the local OIDC server, create
// an engagement, connect it (seed again), add a request item, retrieve the trial balance and
// see the item received, its source, and the agent's screening proposal. Axe runs on the
// engagements page and the board.
import { execFileSync } from "node:child_process";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Playwright runs from apps/web (`make e2e`), so the repo root is two levels up.
const REPO_ROOT = "../..";
const SCREENING_TIMEOUT_MS = 90_000;

async function expectNoSeriousViolations(page: Page): Promise<void> {
  const { violations } = await new AxeBuilder({ page }).analyze();
  const serious = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(
    serious.map((v) => `${v.id} (${v.impact ?? "?"}): ${v.help}`),
    "serious or critical accessibility violations",
  ).toEqual([]);
}

test("ac1 ac18 journey: sign in, create, retrieve, screened", async ({ page }) => {
  const name = `Journey audit ${String(Date.now())}`;

  // AC-1: sign in as the seeded practice leader and land in the firm.
  await page.goto("/");
  await page.getByRole("button", { name: /Dana Leader/ }).click();
  await expect(page.getByText(/Dana Leader · Dev firm/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Engagements" })).toBeVisible();
  await expectNoSeriousViolations(page);

  // Create an engagement.
  await page.getByRole("button", { name: "New engagement" }).first().click();
  await page.getByLabel("Engagement name").fill(name);
  await page.getByLabel("Client", { exact: true }).fill("Journey Client");
  await page.getByLabel("Client entity").fill("Journey Client Inc");
  await page.getByLabel("Fiscal year start").fill("2025-01-01");
  await page.getByLabel("Fiscal year end").fill("2025-12-31");
  await page.getByRole("button", { name: "Create engagement" }).click();
  const link = page.getByRole("link", { name });
  await expect(link).toBeVisible();
  await expectNoSeriousViolations(page);

  // Connect the new client entity to the fake connector (there is no connections UI).
  execFileSync("make", ["seed"], { cwd: REPO_ROOT, stdio: "pipe" });

  // The board: add an item and retrieve.
  await link.click();
  await expect(page.getByRole("heading", { name })).toBeVisible();
  await page.getByLabel("Request", { exact: true }).fill("Trial balance");
  await page.getByLabel("Audit area").fill("Financial reporting");
  await page.getByRole("button", { name: "Add request item" }).click();
  const card = page.getByRole("list", { name: "Request items" }).getByRole("listitem").first();
  await expect(card.getByText("Trial balance", { exact: true })).toBeVisible();
  await card.getByRole("button", { name: "Retrieve trial balance" }).click();

  await expect(card.getByText("Received", { exact: true })).toBeVisible();
  await expect(card.getByText("Retrieved · version 1")).toBeVisible();

  // The worker's agent proposes (fake model): a proposal, with verified citations.
  await expect(card.getByText(/Agent proposes/)).toBeVisible({ timeout: SCREENING_TIMEOUT_MS });
  await expect(card.getByText("Verified", { exact: true }).first()).toBeVisible();
  await expect(card.getByText("Unverified", { exact: true })).toHaveCount(0);
  await expect(
    card.getByRole("button", { name: /accept|approve|reject|waive|confirm/i }),
  ).toHaveCount(0);
  await expectNoSeriousViolations(page);
});
