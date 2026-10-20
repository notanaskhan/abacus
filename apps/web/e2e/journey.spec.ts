// AC-1, AC-18 (TASK-012) and SPEC-045 AC-14 (F-01-T08): the setup-first journey in a real
// browser. Needs `make dev` running and `make seed` done. Sign in through the local OIDC server,
// create an engagement, check its Setup gates (SPEC-025 AC-10), connect it, add a request item on
// the Requests tab, retrieve the trial balance and see the item received, its source, and the
// agent's screening proposal. Every step waits on state, never on time; axe runs after each step.
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

/** Connect every client entity without a connection to the fake connector. There is no
 * connections UI for the firm yet, so this runs the dev seed, which is idempotent: it only adds
 * fake connections that are missing and changes nothing else. Kept as one named step (AC-14). */
function connectNewEntitiesToTheFakeLedger(): void {
  execFileSync("make", ["seed"], { cwd: REPO_ROOT, stdio: "pipe" });
}

test("setup-first journey: create, setup gates, request, retrieve, screened", async ({ page }) => {
  // Unique per run, so a second night never meets "This client may already exist".
  const stamp = String(Date.now());
  const name = `Journey audit ${stamp}`;

  // AC-1: sign in as the seeded practice leader and land in the firm.
  await page.goto("/");
  await page.getByRole("button", { name: /Dana Leader/ }).click();
  await expect(page.getByText(/Dana Leader · Dev firm/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Engagements" })).toBeVisible();
  await expectNoSeriousViolations(page);

  // Create an engagement: it opens on the engagement itself.
  await page.getByRole("button", { name: "New engagement" }).first().click();
  await page.getByLabel("Engagement name").fill(name);
  await page.getByLabel("Client", { exact: true }).fill(`Journey Client ${stamp}`);
  await page.getByLabel("Client entity").fill(`Journey Client ${stamp} Inc`);
  await page.getByLabel("Fiscal year start").fill("2025-01-01");
  await page.getByLabel("Fiscal year end").fill("2025-12-31");
  await page.getByRole("button", { name: "Create engagement" }).click();
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
  const tabs = page.getByRole("navigation", { name: "Engagement" });
  await expectNoSeriousViolations(page);

  // SPEC-025 AC-10: the Setup page shows where setup stands, with the checklist.
  await tabs.getByRole("link", { name: "Setup" }).click();
  await expect(page.getByText("Setup checklist")).toBeVisible();
  await expectNoSeriousViolations(page);

  // SPEC-025: the engagement partner records acceptance and the independence conclusion;
  // retrieval opens only after acceptance.
  const acceptance = page.getByRole("region", { name: "Acceptance and independence conclusion" });
  await acceptance.getByRole("button", { name: "Record" }).click();
  await acceptance
    .getByLabel("Where it's documented")
    .fill("Acceptance memo in the engagement file");
  await acceptance
    .getByRole("checkbox", { name: /I have concluded on compliance with independence/ })
    .check();
  await acceptance.getByRole("button", { name: "Save" }).click();
  await expect(acceptance.getByText("Accepted", { exact: true })).toBeVisible();
  await expectNoSeriousViolations(page);

  // The gate that opens client data to this person (TASK-045): confirm independence.
  const independence = page.getByRole("region", { name: "Independence" });
  await independence.getByRole("button", { name: "Confirm my independence" }).click();
  await expect(independence.getByText("1 of 1 confirmed")).toBeVisible();
  await expectNoSeriousViolations(page);

  connectNewEntitiesToTheFakeLedger();

  // The Requests tab: add an item and retrieve.
  await tabs.getByRole("link", { name: "Requests" }).click();
  await page.getByLabel("Request", { exact: true }).fill("Trial balance");
  await page.getByLabel("Audit area").fill("Financial reporting");
  await page.getByRole("button", { name: "Add request item" }).click();
  const card = page.getByRole("list", { name: "Request items" }).getByRole("listitem").first();
  await expect(card.getByText("Trial balance", { exact: true })).toBeVisible();
  await expectNoSeriousViolations(page);
  await card.getByRole("button", { name: "Retrieve trial balance" }).click();

  // The plan's request words (TASK-105): a received request reads "Uploaded".
  await expect(card.getByText("Uploaded", { exact: true })).toBeVisible();
  await expect(card.getByText("Retrieved · version 1")).toBeVisible();
  await expectNoSeriousViolations(page);

  // The worker's agent proposes (fake model): a proposal, with verified citations.
  await expect(card.getByText(/Agent proposes/)).toBeVisible({ timeout: SCREENING_TIMEOUT_MS });
  await expect(card.getByText("Verified", { exact: true }).first()).toBeVisible();
  await expect(card.getByText("Unverified", { exact: true })).toHaveCount(0);
  await expect(
    card.getByRole("button", { name: /accept|approve|reject|waive|confirm/i }),
  ).toHaveCount(0);
  await expectNoSeriousViolations(page);
});
