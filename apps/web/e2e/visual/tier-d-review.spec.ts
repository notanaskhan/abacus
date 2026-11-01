// Tier D for the review grammar's overlays (P-04-T58; P-04 §3 "Kit / preset"): computed geometry,
// not pixels, so it needs no baseline and blocks wherever the visual project runs. O1: SHL-09's
// 420 tray; O2: SHL-16's 480 right drawer; O3: the 500 sheet 52 below the top for SHL-10, SHL-11,
// SHL-12 and SHL-15, with the dialog radius 14 (shared context: dialogs 14).
import { type Locator, type Page, expect, test } from "@playwright/test";

test.use({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, reducedMotion: "reduce" });

async function layer(page: Page, screen: string, st: string): Promise<Locator> {
  await page.goto(`/components/screens/${screen}?st=${st}&frame=1`);
  const found = page.locator("[data-overlay]").last();
  await expect(found).toBeVisible();
  return found;
}

async function box(target: Locator): Promise<{ x: number; y: number; w: number; h: number }> {
  const b = await target.boundingBox();
  if (b === null) throw new Error("no box");
  return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) };
}

for (const screen of ["SHL-10", "SHL-11", "SHL-12", "SHL-15"] as const) {
  test(`${screen}a: O3 sheet 500 wide, 52 below the top, radius 14`, async ({ page }) => {
    const sheet = await layer(page, screen, "a");
    const { y, w } = await box(sheet);
    expect(w).toBe(500);
    expect(y).toBe(52);
    const radius = await sheet.evaluate((el) => getComputedStyle(el).borderTopLeftRadius);
    expect(radius).toBe("14px");
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
  const tray = await layer(page, "SHL-09", "a");
  expect((await box(tray)).w).toBe(420);
});
