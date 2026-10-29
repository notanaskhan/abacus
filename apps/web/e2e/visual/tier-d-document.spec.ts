// Tier D for the T10 DocumentOnWell board (F-06-T14; F-06.md §5.4 "Computed geometry"): exact
// computed sizes, not pixels, so it needs no baseline and blocks wherever the visual project runs.
// From the T10 handoff spec: the 470 structure pane beside the 896 paper pane, whose header is 46
// and whose well centres the 600 paper card; KV rows 33, section bands 31, the crumb header 32.
import { type Locator, expect, test } from "@playwright/test";
import { openGallery } from "./support";

async function size(target: Locator): Promise<{ width: number; height: number }> {
  const box = await target.first().boundingBox();
  if (box === null) throw new Error("no box");
  return { width: Math.round(box.width), height: Math.round(box.height) };
}

for (const st of ["a", "b"] as const) {
  test(`T10${st}: structure 470, paper pane 896, paper 600, header 46`, async ({ page }) => {
    await openGallery(page, `screens/T10?st=${st}`);
    const frame = page.locator(`[data-artboard='${st}'] [data-template='t10']`);
    await expect(frame).toBeVisible();
    const panes = frame.locator("[data-shell='pane']");
    expect((await size(panes.nth(0))).width).toBe(470);
    expect((await size(panes.nth(1))).width).toBe(896);
    expect((await size(panes.nth(1).locator("[data-shell='pane-header']"))).height).toBe(46);
    expect((await size(frame.locator("[data-document='paper']"))).width).toBe(600);
    expect((await size(frame.locator("[data-document='kv-sheet'] > div").first())).height).toBe(32);
    expect((await size(frame.locator("[data-document='kv-sheet'] h3").first())).height).toBe(31);
    expect((await size(frame.locator("[data-document='kv-sheet'] li").first())).height).toBe(33);
  });
}
