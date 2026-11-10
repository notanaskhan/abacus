// EBP keyboard (A-05-T51) on fixtures: Escape closes what a canvas opens, and focus goes back to the
// control that opened it. Parity's Tier C and D reports run in e2e/parity and e2e/visual.
import { expect, test } from "@playwright/test";

test.use({ reducedMotion: "reduce" });

for (const n of ["01", "03", "04"]) {
  test(`EBP-${n}: Escape closes a dialog and focus returns`, async ({ page }) => {
    await page.goto(`/audits/_auditId_?screen=EBP-${n}&st=a&section=ebp_${n}`);
    const canvas = page.locator(`[data-screen='EBP-${n}']`).first();
    await expect(canvas).toBeVisible();
    const opener = canvas.locator("button[aria-haspopup='dialog']:not([disabled])").first();
    test.skip((await opener.count()) === 0, "this artboard opens nothing");
    await opener.click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(opener).toBeFocused();
  });
}
