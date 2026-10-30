// ac-test-author: ayushkbhatia
// F-06-T13 (F-06.md §10 item 1; Stories 2.1 to 2.5): the f06-tax-index specimen walk in fixture
// mode on the /components gallery, Hannah Leclerc at E0 (Mon Sep 14, 2026, 9:24 AM CT), axe on
// every step and INV-1 to INV-5 asserted. TPL-01a → b (the Awaiting signature tile) → c (search)
// → d (never-resolving) → e (season start); the due popover from the keyboard.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/specimens/f06-tax-index.spec.ts`.
import { type Page, expect, test } from "@playwright/test";
import { axeStep } from "../harness/axe";
import { assertInvariants } from "../harness/invariants";
import { persona } from "../harness/personas";

const HANNAH = persona("hannah-leclerc");
const E0 = new Date("2026-09-14T09:24:00-05:00");

test.use({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });

async function board(page: Page, st: string): Promise<void> {
  await page.clock.setFixedTime(E0);
  await page.goto(`/components/screens/TPL-01?st=${st}&frame=1&static=1&as=hannah-leclerc`);
  await expect(
    page.locator(`[data-artboard='tpl-01${st}'] [data-specimen='tpl-01']`),
  ).toBeVisible();
}

async function step(page: Page, name: string): Promise<void> {
  await axeStep(page, `f06-tax-index ${name}`, { include: "[data-artboard]" });
  await assertInvariants(page, { step: `f06-tax-index ${name}`, persona: HANNAH });
}

test("test_ac9_a_default_board_reads_the_server_counts", async ({ page }) => {
  await board(page, "a");
  await expect(
    page.getByText("79 open · 145 done · 224 TY2025 returns · 161 extended"),
  ).toBeVisible();
  await expect(page.getByText("Showing 15 of 79 open")).toBeVisible();
  for (const [label, n] of [
    ["Prepared", "17"],
    ["In review", "15"],
    ["Issues", "11"],
    ["Ready", "7"],
    ["Gathering", "8"],
    ["Preparing", "9"],
    ["Awaiting signature", "10"],
    ["Filed · Accepted", "145"],
  ] as const) {
    await expect(
      page.getByRole("button", { name: new RegExp(`${n}.*${label}|${label}.*${n}`) }),
    ).toBeVisible();
  }
  // The window frames the board with Tax Returns lit in the firm toolbar.
  await expect(page.locator("[data-artboard='a'] [data-shell='app']")).toBeVisible();
  await step(page, "TPL-01a");
});

test("test_ac10_b_the_awaiting_signature_tile_filters_to_e1_e10", async ({ page }) => {
  await board(page, "a");
  await page
    .getByRole("button", { name: /Awaiting signature/ })
    .first()
    .click();
  await expect(page.getByText(/Showing 10 of 10/)).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Signature" })).toBeVisible();
  await board(page, "b");
  await expect(page.getByText(/Showing 10 of 10/)).toBeVisible();
  await step(page, "TPL-01b");
});

test("test_ac11_due_cell_explains_its_rule_from_the_keyboard", async ({ page }) => {
  await board(page, "a");
  const due = page.getByRole("button", { name: "Sep 15", exact: true }).first();
  await due.focus();
  await page.keyboard.press("Enter");
  const popover = page.getByRole("dialog", { name: /^Due date rule for / });
  await expect(popover).toBeVisible();
  await expect(popover).toContainText(/month/);
  await expect(page.getByText("Ext.").first()).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Due" })).toBeVisible();
  await expect(page.getByText(/deadline/i)).toHaveCount(0);
});

test("test_ac12_c_d_e_empty_loading_and_season_start", async ({ page }) => {
  await board(page, "c");
  await expect(page.getByText("No results for 'Schwab'.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Clear filters" })).toBeVisible();
  await expect(page.getByText(/^Showing /)).toHaveCount(0);
  await step(page, "TPL-01c");

  await board(page, "d");
  await expect(page.getByRole("columnheader", { name: "Return" })).toBeVisible();
  await expect(page.getByText(/^Showing /)).toHaveCount(0);
  await expect(page.getByText("Ridgeline Property Partners, LP")).toHaveCount(0);
  await step(page, "TPL-01d");

  await board(page, "e");
  await expect(page.getByText("No TY2026 returns yet.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Open season setup" })).toBeVisible();
  await step(page, "TPL-01e");
});

test("test_ac13_sync_chips_and_bulk_actions_are_callbacks", async ({ page }) => {
  await board(page, "a");
  await expect(page.getByText("Synced Sep 11").first()).toBeVisible();
  await page.getByRole("button", { name: "Bulk actions" }).click();
  for (const item of ["Assign preparer…", "Extend…", "Run firm standards…"]) {
    await expect(page.getByRole("menuitem", { name: item })).toBeVisible();
  }
});
