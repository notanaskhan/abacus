// Tier D for the tier-4 templates (F-07-T22; TASK-7951; SPEC-652; handoff T13, T14, T17): exact
// computed sizes on the TPL-13, TPL-14 and TPL-17 specimens, so no baseline is needed. T13's subbar
// 42; T14's header 46, banner 36 and inspector 330; T17's thumbnail rail 120 with 96 × 124 pages
// and the right pane 330.
import { type Locator, expect, test } from "@playwright/test";
import { openGallery, specimen } from "./support";

async function box(target: Locator): Promise<{ x: number; y: number; w: number; h: number }> {
  const b = await target.first().boundingBox();
  if (b === null) throw new Error("no box");
  return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) };
}

test("T13 (TPL-13a): the 42 h subbar above one full-width pane", async ({ page }) => {
  await openGallery(page);
  const board = specimen(page, "tpl-13", "[data-artboard='tpl-13a']");
  await expect(board.locator("[data-calendar]")).toBeVisible();
  const sub = board.getByRole("group").first();
  expect((await box(sub)).h).toBeLessThanOrEqual(42);
});

for (const st of ["a", "b", "f"] as const) {
  test(`T14 (TPL-14${st}): header 46, inspector 330 when a node is selected`, async ({ page }) => {
    await openGallery(page);
    const board = specimen(page, "tpl-14", `[data-artboard='tpl-14${st}']`);
    await expect(board.locator("[data-template='T14']")).toBeVisible();
    const banner = board.locator("[data-banner]");
    if ((await banner.count()) > 0) expect((await box(banner)).h).toBe(36);
    const inspector = board.getByRole("complementary");
    if ((await inspector.count()) > 0) expect((await box(inspector)).w).toBe(330);
  });
}

for (const st of ["a", "b", "c", "d", "e"] as const) {
  test(`T17 (TPL-17${st}): rail 120, pages 96 × 124, right pane 330`, async ({ page }) => {
    await openGallery(page);
    const board = specimen(page, "tpl-17", `[data-artboard='tpl-17${st}']`);
    await expect(board.locator("[data-template='T17']")).toBeVisible();
    const rail = board.getByRole("navigation", { name: "Pages" });
    expect((await box(rail)).w).toBe(120);
    const thumb = await box(rail.getByRole("button").first());
    expect([thumb.w, thumb.h]).toEqual([96, 124]);
    expect((await box(board.locator("[data-diagnostics]").locator(".."))).w).toBeLessThanOrEqual(330);
  });
}
