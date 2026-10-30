// ac-test-author: ayushkbhatia
// F-06-T18 (F-06.md §10 item 1, Stories 5.1 to 5.4 and 5.7; SPEC-400 AC-26 to AC-29, AC-32): the T6
// steps of the f06-workbook walk in fixture mode on the gallery at E0, axe on each step (serious
// and critical block). TPL-06a–e and T6d/e join with F-06-T19 and T20.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/specimens/f06-workbook.spec.ts`.
import { type Page, expect, test } from "@playwright/test";
import { axeStep } from "../harness/axe";
import { assertInvariants } from "../harness/invariants";
import { persona } from "../harness/personas";

const SAMUEL = persona("samuel-ito");
const E0 = new Date("2026-09-14T09:24:00-05:00");

test.use({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });

async function board(page: Page, st: string): Promise<void> {
  await page.clock.setFixedTime(E0);
  await page.goto(`/components/screens/T6?st=${st}&frame=1&static=1`);
  await expect(page.locator(`[data-artboard='${st}'] [data-template='t6']`)).toBeVisible();
}

test("test_ac26_t6a_tab_groups_one_row_at_1400_and_every_pill_ties", async ({ page }) => {
  await board(page, "a");
  const bar = page.locator("[data-workbook='tabsbar']");
  await expect(bar).toHaveCSS("height", "50px");
  const lists = bar.getByRole("tablist");
  await expect(lists).toHaveCount(2);
  const [first, second] = [await lists.nth(0).boundingBox(), await lists.nth(1).boundingBox()];
  expect(first).not.toBeNull();
  expect(second).not.toBeNull();
  // Both groups on one row: same vertical centre, the second starting after the first.
  expect(Math.abs((first?.y ?? 0) - (second?.y ?? 0))).toBeLessThan(1);
  expect((second?.x ?? 0) + (second?.width ?? 0)).toBeLessThanOrEqual(1400 + 20);
  const strip = page.getByRole("list", { name: "Checks" });
  await expect(strip.getByText("tie", { exact: true })).toHaveCount(4);
  await expect(page.getByText("GP", { exact: true })).toBeVisible();
  await axeStep(page, "f06-workbook T6a", { include: "[data-artboard]" });
  await assertInvariants(page, { step: "f06-workbook T6a", persona: SAMUEL });
});

test("test_ac27_t6b_off_links_issue_2_through_the_callback", async ({ page }) => {
  await board(page, "b");
  const strip = page.getByRole("list", { name: "Checks" });
  await expect(strip.getByText("off 6,200")).toBeVisible();
  await strip.getByRole("button", { name: /Issue 2/ }).click();
  await expect(page.locator("[data-artboard='b']")).toHaveAttribute("data-opened-issue", "2");
  // By movement: each variance state says itself in words.
  for (const word of ["Explained", "Unexplained", "Within threshold", "Exception"]) {
    await expect(page.getByText(word, { exact: true }).first()).toBeAttached();
  }
  await expect(page.getByText("Ties once posted")).toBeVisible();
  await axeStep(page, "f06-workbook T6b", { include: "[data-artboard]" });
  await assertInvariants(page, { step: "f06-workbook T6b", persona: SAMUEL });
});

test("test_ac29_t6c_building_pending_pills_skeletons_no_sign_off", async ({ page }) => {
  await board(page, "c");
  const strip = page.getByRole("list", { name: "Checks" });
  await expect(strip.getByText("Pending", { exact: true })).toHaveCount(4);
  await expect(page.getByText("Workbook agent is running")).toBeVisible();
  await expect(page.locator("[data-workbook='skeleton-row']")).toHaveCount(7);
  await expect(page.getByRole("button", { name: "Sign off…" })).toHaveCount(0);
  await axeStep(page, "f06-workbook T6c", { include: "[data-artboard]" });
  await assertInvariants(page, { step: "f06-workbook T6c", persona: SAMUEL });
});

test("test_ac26_geometry_control_bar_44_tally_52_panes_y244", async ({ page }) => {
  await board(page, "a");
  await expect(page.locator("[data-workbook='control-bar']")).toHaveCSS("height", "44px");
  await expect(page.locator("[data-workbook='tally']")).toHaveCSS("height", "52px");
  const shell = await page.locator("[data-shell='app']").boundingBox();
  const pane = await page.locator("[data-workbook='pane']").first().boundingBox();
  expect(Math.round((pane?.y ?? 0) - (shell?.y ?? 0))).toBe(244);
  expect(Math.round((pane?.y ?? 0) + (pane?.height ?? 0) - (shell?.y ?? 0))).toBe(848);
});
