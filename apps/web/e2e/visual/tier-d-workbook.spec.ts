// Tier D for the T6 WorkbookLayout boards and the TPL-06 specimen (F-06-T22; F-06.md §5.4
// "Computed geometry"): exact computed sizes, not pixels, so it needs no baseline and blocks
// wherever the visual project runs. From the T6 handoff spec: tabsbar 50, control bar 44, tally
// strip 52 in the shell's tabs slot, panes from y244 to y848 of the 860 window.
import { type Locator, expect, test } from "@playwright/test";
import { openGallery } from "./support";

async function box(target: Locator): Promise<{ y: number; height: number }> {
  const b = await target.first().boundingBox();
  if (b === null) throw new Error("no box");
  return { y: Math.round(b.y), height: Math.round(b.height) };
}

for (const screen of ["T6", "TPL-06"] as const) {
  for (const st of ["a", "b", "c", "d", "e"] as const) {
    test(`${screen}${st}: tabsbar 50, control bar 44, tally 52, panes y244–848`, async ({
      page,
    }) => {
      await openGallery(page, `screens/${screen}?st=${st}`);
      const frame = page.locator(`[data-artboard='${st}']`);
      await expect(frame.locator("[data-template='t6']")).toBeVisible();
      expect((await box(frame.locator("[data-workbook='tabsbar']"))).height).toBe(50);
      expect((await box(frame.locator("[data-workbook='control-bar']"))).height).toBe(44);
      expect((await box(frame.locator("[data-workbook='tally']"))).height).toBe(52);
      const shell = await box(frame.locator("[data-shell='app']"));
      const pane = await box(frame.locator("[data-workbook='pane']"));
      expect(pane.y - shell.y).toBe(244);
      expect(pane.y + pane.height - shell.y).toBe(848);
    });
  }
}
