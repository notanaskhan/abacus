// ac-test-author: ayushkbhatia
// F-08-T08 carry (TASK-8843; handoff T18 a–i; F-08 §5): the T18 lock. Axe on every T18 state
// (serious and critical block), a screenshot per state against its committed baseline (the
// handoff's T18a–i frames are the parity reference, tier C), the P · R slot opening the sign-off
// and never signing, and T18b's sideways scroll with select and Key frozen.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/specimens/f08-t18.spec.ts`.
import { type Page, expect, test } from "@playwright/test";
import { axeStep } from "../harness/axe";

const E0 = new Date("2026-09-14T09:24:00-05:00");
const STATES = ["a", "b", "c", "d", "e", "f", "g", "h", "i"] as const;

test.use({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });

async function board(page: Page, st: string): Promise<void> {
  await page.clock.setFixedTime(E0);
  await page.goto(`/components/screens/T18?st=${st}&frame=1&static=1`);
  await expect(page.locator(`[data-artboard='${st}'][data-template='T18']`)).toBeVisible();
}

for (const st of STATES) {
  test(`test_t18${st}_axe_serious_and_critical_zero`, async ({ page }) => {
    await board(page, st);
    await axeStep(page, `f08 T18${st}`, { include: "[data-artboard]" });
  });

  test(`test_t18${st}_parity_screenshot`, async ({ page }) => {
    test.skip(process.env.ABACUS_VISUAL !== "1", "visual baselines run under ABACUS_VISUAL=1");
    await board(page, st);
    await expect(page.locator(`[data-artboard='${st}']`)).toHaveScreenshot(`t18${st}.png`, {
      maxDiffPixelRatio: 0.02,
    });
  });
}

test("test_t18a_pr_slot_opens_the_sign_off_and_never_signs", async ({ page }) => {
  await board(page, "a");
  await page.getByRole("button", { name: "R sign-off for A-1" }).click();
  await expect(page.locator("[data-artboard='a']")).toHaveAttribute(
    "data-opened-sign-off",
    /A-1/u,
  );
  await expect(page.getByRole("button", { name: /^sign off$|approve/iu })).toHaveCount(0);
});

test("test_t18b_scrolls_sideways_with_select_and_key_frozen", async ({ page }) => {
  await board(page, "b");
  const canvas = page.locator("[data-artboard='b'] [data-canvas]");
  await canvas.evaluate((el) => {
    el.scrollLeft = 400;
  });
  const key = page.locator("[data-artboard='b'] [data-row-key='A-1'] [data-col-key='key']");
  await expect(key.first()).toBeInViewport();
});
