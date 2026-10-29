// Tier D for HOME-01 lite (I-01-T14; docs/screens/HOME-01.md; the I-01 row): the frame's computed
// geometry on the gallery artboard, not pixels, so it needs no baseline and blocks where the
// visual project runs: subbar 42, tiles 120 × 99 at radius 14, pane header 46, rows 44 (Client
// activity) and the right column 420.
import { type Locator, type Page, expect, test } from "@playwright/test";

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1,
  reducedMotion: "reduce",
});

async function open(page: Page, st: string): Promise<Locator> {
  await page.goto(`/components/screens/HOME-01?st=${st}&frame=1&static=1`);
  const app = page.locator(`[data-artboard='${st}'] [data-shell='app']`).first();
  await expect(app).toBeVisible();
  return app;
}

async function box(target: Locator): Promise<{ width: number; height: number }> {
  const b = await target.first().boundingBox();
  if (b === null) throw new Error("no box");
  return { width: Math.round(b.width), height: Math.round(b.height) };
}

for (const st of ["a", "a2", "f", "g"]) {
  test(`HOME-01 ${st}: subbar 42, tiles 120x99 r14, pane header 46, side 420`, async ({
    page,
  }) => {
    const app = await open(page, st);
    expect((await box(app.locator("[data-dashboard='subbar']"))).height).toBe(42);
    // g is the loading state: skeleton bars stand where the tiles go (aria-busy), no tile yet.
    if (st === "g") {
      await expect(app.locator("[data-dashboard='tiles'][aria-busy='true']")).toBeVisible();
    } else {
      const tile = app.locator("[data-dashboard='tiles'] [data-tile]").first();
      expect(await box(tile)).toEqual({ width: 120, height: 99 });
      expect(await tile.evaluate((el) => getComputedStyle(el).borderTopLeftRadius)).toBe("14px");
    }
    expect((await box(app.locator("[data-shell='pane-header']"))).height).toBe(46);
    expect((await box(app.locator("[data-dashboard='side']"))).width).toBe(420);
  });
}

test("HOME-01 a: Client activity rows are 44", async ({ page }) => {
  const app = await open(page, "a");
  const rows = app.locator("[data-home='activity'] > li");
  expect(await rows.count()).toBeGreaterThan(0);
  for (const row of await rows.all()) expect((await box(row)).height).toBeGreaterThanOrEqual(44);
});
