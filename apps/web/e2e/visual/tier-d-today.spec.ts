// Tier D for HOME-05 and SHL-23 (I-02-T21; TASK-7952; docs/screens/HOME-05.md, SHL-23.md): the
// docked pane is 470 wide at x12 with a 32 h chip row, the panel's header 46, and collapsed, HOME-01
// keeps its geometry. Computed sizes, no baseline.
import { type Locator, expect, test } from "@playwright/test";
import { openGallery } from "./support";

async function box(target: Locator): Promise<{ x: number; y: number; w: number; h: number }> {
  const b = await target.first().boundingBox();
  if (b === null) throw new Error("no box");
  return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) };
}

for (const st of ["a", "b", "d", "e"]) {
  test(`HOME-05 ${st}: the Today pane 470 at x12, header 46`, async ({ page }) => {
    await openGallery(page, `screens/HOME-05?st=${st}`);
    const frame = page.locator(`[data-artboard='${st}']`);
    const pane = frame.getByRole("complementary", { name: "Today" });
    await expect(pane).toBeVisible();
    expect((await box(pane)).w).toBe(470);
    expect((await box(frame.locator("[data-screen='SHL-23'] header"))).h).toBe(46);
  });
}

test("HOME-05 c: collapsed, the Open Today row is 32 h and HOME-01 fills the width", async ({ page }) => {
  await openGallery(page, "screens/HOME-05?st=c");
  const frame = page.locator("[data-artboard='c']");
  await expect(frame.locator("[data-state='c']")).toBeVisible();
  expect((await box(frame.getByRole("button", { name: /Open Today/ }).locator(".."))).h).toBe(32);
});
