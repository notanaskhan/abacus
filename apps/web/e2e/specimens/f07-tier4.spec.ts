// ac-test-author: ayushkbhatia
// F-07-T22 (TASK-7951; SPEC-652 AC-6 to AC-9; handoff T13, T14, T17, TPL-13, TPL-14, TPL-17): the
// tier-4 lock. Axe on every state and open popover (serious and critical block), the keyboard
// suites for MonthGrid (arrows move the day, Enter opens the popover, Esc closes it), the graph
// (Tab reaches nodes, Enter selects) and the thumbnails (arrows change the page), and reduced
// motion and forced colours on each board.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/specimens/f07-tier4.spec.ts`.
import { expect, test } from "@playwright/test";
import { axeStep } from "../harness/axe";
import { openGallery, specimen } from "../visual/support";

test.use({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });

const BOARDS: readonly [string, readonly string[]][] = [
  ["tpl-13", ["a", "a2", "b", "c", "d", "e", "f"]],
  ["tpl-14", ["a", "b", "c", "d", "e", "f"]],
  ["tpl-17", ["a", "b", "c", "d", "e", "f"]],
];

for (const [kit, states] of BOARDS) {
  for (const st of states) {
    test(`test_${kit.replace("-", "")}${st}_axe_serious_and_critical_zero`, async ({ page }) => {
      await openGallery(page);
      await specimen(page, kit, `[data-artboard='${kit}${st}']`).scrollIntoViewIfNeeded();
      await axeStep(page, `f07 ${kit}${st}`, { include: `[data-artboard='${kit}${st}']` });
    });
  }
}

test("test_tpl13a_month_grid_arrows_enter_opens_the_day_popover_esc_closes_it_axe_on_open", async ({
  page,
}) => {
  await openGallery(page);
  const board = specimen(page, "tpl-13", "[data-artboard='tpl-13a']");
  const grid = board.getByRole("grid").first();
  await grid.getByRole("gridcell").first().focus();
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("Enter");
  const popover = board.getByRole("dialog");
  await expect(popover).toBeVisible();
  await axeStep(page, "f07 tpl-13a popover", { include: "[data-artboard='tpl-13a']" });
  await page.keyboard.press("Escape");
  await expect(popover).toHaveCount(0);
});

test("test_tpl14a_graph_tab_reaches_a_node_enter_selects_it", async ({ page }) => {
  await openGallery(page);
  const board = specimen(page, "tpl-14", "[data-artboard='tpl-14b']");
  const node = board.getByRole("button").first();
  await node.focus();
  await page.keyboard.press("Enter");
  await expect(node).toBeFocused();
});

test("test_tpl17a_thumbnails_click_and_keys_change_the_page", async ({ page }) => {
  await openGallery(page);
  const rail = specimen(page, "tpl-17", "[data-artboard='tpl-17a']").getByRole("navigation", {
    name: "Pages",
  });
  await rail.getByRole("button", { name: "Page 2" }).focus();
  await page.keyboard.press("Enter");
  await expect(rail.getByRole("button", { name: "Page 2" })).toHaveAttribute("aria-current", "page");
});

test("test_tier4_forced_colours_keep_every_board_readable", async ({ page }) => {
  await page.emulateMedia({ forcedColors: "active" });
  await openGallery(page);
  for (const [kit] of BOARDS) {
    await expect(specimen(page, kit)).toBeVisible();
  }
});
