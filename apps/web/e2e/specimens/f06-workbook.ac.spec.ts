// ac-test-author: notanaskhan (ADR-078 independent suite, built in the S21 solo lane)
// F-06-T21 (TASK-2607; SPEC-400 AC-26, AC-29 to AC-31; F-06.md §3 F5 Stories 5.1, 5.4 to 5.6):
// what needs a browser. Reduced motion leaves no running animation (the 45 ms row stagger is
// gone), the pane scroller and the calc tree work by keyboard, building enables no sign-off, and
// the chips read P before R. Fixture mode on the gallery at E0; axe on each board.
// Run: `pnpm -C apps/web exec playwright test --project fixture e2e/specimens/f06-workbook.ac.spec.ts`.
import { type Page, expect, test } from "@playwright/test";
import { axeStep } from "../harness/axe";

const E0 = new Date("2026-09-14T09:24:00-05:00");

test.use({ viewport: { width: 1440, height: 900 } });

async function board(page: Page, screen: "T6" | "TPL-06", st: string): Promise<void> {
  await page.clock.setFixedTime(E0);
  await page.goto(`/components/screens/${screen}?st=${st}&frame=1`);
  await expect(page.locator(`[data-artboard='${st}']`)).toBeVisible();
}

test.describe("reduced motion", () => {
  test.use({ reducedMotion: "reduce" });

  for (const [screen, st] of [
    ["T6", "a"],
    ["T6", "b"],
    ["TPL-06", "a"],
    ["TPL-06", "c"],
  ] as const) {
    test(`test_ac29_reduced_motion_leaves_no_animation_on_${screen}_${st}`, async ({ page }) => {
      await board(page, screen, st);
      await expect.poll(() => page.evaluate(() => document.getAnimations().length)).toBe(0);
    });
  }
});

test("test_ac26_the_by_partner_scroller_moves_by_keyboard", async ({ page }) => {
  await board(page, "TPL-06", "c");
  const scroller = page.getByRole("region", { name: "Partners" });
  await scroller.focus();
  await expect(scroller).toBeFocused();
  const before = await scroller.evaluate((el) => el.scrollLeft);
  await page.keyboard.press("ArrowRight");
  await expect.poll(() => scroller.evaluate((el) => el.scrollLeft)).toBeGreaterThan(before);
  await page.keyboard.press("ArrowLeft");
  await expect.poll(() => scroller.evaluate((el) => el.scrollLeft)).toBeLessThan(before + 1);
  await axeStep(page, "f06-workbook.ac TPL-06c", { include: "[data-artboard]" });
});

test("test_ac29_building_enables_no_sign_off_anywhere", async ({ page }) => {
  for (const [screen, st] of [
    ["T6", "c"],
    ["TPL-06", "d"],
  ] as const) {
    await board(page, screen, st);
    const enabled = page.getByRole("button", { name: /Sign off/ }).and(page.locator(":enabled"));
    await expect(enabled).toHaveCount(0);
    await expect(page.getByText("Workbook agent is running").first()).toBeVisible();
  }
});

test("test_ac30_t6d_chips_read_ob_then_dr_and_open_the_dialog", async ({ page }) => {
  await board(page, "T6", "d");
  const chips = page.getByRole("group", { name: "Sign-offs" }).getByRole("button");
  await expect(chips).toHaveCount(2);
  await expect(chips.nth(0)).toContainText("OB");
  await expect(chips.nth(1)).toContainText("DR");
  await axeStep(page, "f06-workbook.ac T6d", { include: "[data-artboard]" });
});

test("test_ac31_t6e_the_calc_tree_by_keyboard_lights_pins_and_escapes", async ({ page }) => {
  await board(page, "T6", "e");
  const tree = page.getByRole("tree");
  const first = tree.getByRole("treeitem").first();
  await first.focus();
  await page.keyboard.press("ArrowDown");
  const step = tree.getByRole("treeitem").nth(1);
  await expect(step).toBeFocused();
  // Focus lights the step's workbook cell within the 360 ms fade.
  await expect(page.locator("[data-match-kind='cell'][data-lit]")).toHaveCount(1, {
    timeout: 1000,
  });
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab"); // leave the step: the pinned match stays
  await expect(page.locator("[data-match-kind='cell'][data-lit]")).toHaveCount(1);
  await page.keyboard.press("Escape");
  await expect(step).toBeFocused();
  await axeStep(page, "f06-workbook.ac T6e", { include: "[data-artboard]" });
});
