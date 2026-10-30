// Tier D for AUD-06 and POR-16 (A-02-T31; the contracts' "Template and host frame" rows): the
// frames' computed geometry on the gallery artboards, not pixels, so it needs no baseline and
// blocks where the visual project runs.
// - AUD-06 (T2 audit split inside the AUD-02 cockpit): audit bar 59, rail 330, workpaper 536,
//   viewer 490.
// - POR-16 (T7 reduced): one centred pane 720 under the portal toolbar, no rail.
import { type Locator, type Page, expect, test } from "@playwright/test";

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1,
  reducedMotion: "reduce",
});

async function open(page: Page, id: string, st: string): Promise<Locator> {
  await page.goto(`/components/screens/${id}?st=${st}&frame=1&static=1`);
  const app = page.locator(`[data-artboard='${st}'] [data-shell='app']`).first();
  await expect(app).toBeVisible();
  return app;
}

async function size(target: Locator): Promise<{ width: number; height: number }> {
  const box = await target.first().boundingBox();
  if (box === null) throw new Error("no box");
  return { width: Math.round(box.width), height: Math.round(box.height) };
}

// DEC-832's open gap, closed: the Trial Balance row widens the dock to `--ev-w` as AUD-03 does.
for (const st of ["a", "c", "e"] as const) {
  test(`AUD-06 ${st}: audit bar 59, rail 330, workpaper 536, viewer 490`, async ({ page }) => {
    const app = await open(page, "AUD-06", st);
    expect((await size(app.locator("[data-shell='record-header']"))).height).toBe(59);
    expect((await size(app.locator("[data-cockpit='rail']"))).width).toBe(330);
    expect((await size(app.locator("[data-cockpit='canvas']"))).width).toBe(536);
    expect((await size(app.locator("[data-cockpit='dock']"))).width).toBe(490);
  });
}

for (const st of ["a", "c", "d", "g"] as const) {
  test(`POR-16 ${st}: one pane 720, no rail`, async ({ page }) => {
    const app = await open(page, "POR-16", st);
    expect(await app.locator("[data-portal='rail']").count()).toBe(0);
    expect((await size(app.locator("[data-portal='main']"))).width).toBe(720);
  });
}
