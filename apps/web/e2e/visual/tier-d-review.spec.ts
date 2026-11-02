// Tier D for the review grammar's overlays (P-04-T58; P-04 §3 "Kit / preset"): computed geometry,
// not pixels, so it needs no baseline and blocks wherever the visual project runs. O1: SHL-09's
// 420 tray; O2: SHL-16's 480 right drawer; O3: the 500 sheet 52 below the top for SHL-10, SHL-11,
// SHL-12 and SHL-15, rounded 16 16 0 0 as each screen's handoff spec draws it ("SHEET x450–950,
// top 52, radius 16 16 0 0"; the dialogs' 14 is O4's and C-22's, not the sheet's; TASK-2927).
import { type Locator, type Page, expect, test } from "@playwright/test";

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

async function layer(
  page: Page,
  screen: string,
  st: string,
  selector = "[data-overlay]",
): Promise<Locator> {
  await page.goto(`/components/screens/${screen}?st=${st}&frame=1`);
  const found = page.locator(selector).last();
  await expect(found).toBeVisible();
  return found;
}

async function box(target: Locator): Promise<{ x: number; y: number; w: number; h: number }> {
  const b = await target.boundingBox();
  if (b === null) throw new Error("no box");
  return {
    x: Math.round(b.x),
    y: Math.round(b.y),
    w: Math.round(b.width),
    h: Math.round(b.height),
  };
}

for (const screen of ["SHL-10", "SHL-11", "SHL-12", "SHL-15"] as const) {
  test(`${screen}a: O3 sheet 500 wide, 52 below the top, top radius 16`, async ({ page }) => {
    const sheet = await layer(page, screen, "a");
    const { y, w } = await box(sheet);
    expect(w).toBe(500);
    expect(y).toBe(52);
    const radius = await sheet.evaluate((el) => getComputedStyle(el).borderTopLeftRadius);
    expect(radius).toBe("16px");
  });
}

test("SHL-16a: O2 drawer 480 wide on the right edge", async ({ page }) => {
  const drawer = await layer(page, "SHL-16", "a");
  const { x, w } = await box(drawer);
  expect(w).toBe(480);
  expect(x + w).toBeLessThanOrEqual(1440);
  expect(x + w).toBeGreaterThanOrEqual(1420);
});

test("SHL-09a: O1 tray 420 wide", async ({ page }) => {
  // The artboard places the tray where its popover sits, without the E2 host: the tray itself.
  const tray = await layer(page, "SHL-09", "a", '[data-shl09="tray"]');
  expect((await box(tray)).w).toBe(420);
});
