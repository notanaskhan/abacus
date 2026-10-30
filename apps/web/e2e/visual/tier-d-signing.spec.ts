// Tier D for the signing and tax-index lock (F-06-T13; F-06.md §5.4 "Computed geometry"): exact
// computed sizes of T16, TPL-16 and the TPL-01 frame, not pixels, so it needs no baseline and
// blocks wherever the visual project runs. Numbers from F-06 §5.4 and the T16/TPL-16 handoff specs:
// documents 240, page well 816 holding the 680 page, steps 300, envelope header 46, document rows
// 64; at 390 the phone frame and the 64 sticky bar with its 48 primary; TPL-01 in the 1400 × 860
// window.
import { type Locator, type Page, expect, test } from "@playwright/test";
import { openGallery, specimen } from "./support";

interface Size {
  width: number;
  height: number;
}

async function size(target: Locator): Promise<Size> {
  const box = await target.first().boundingBox();
  if (box === null) throw new Error("no box");
  return { width: Math.round(box.width), height: Math.round(box.height) };
}

/** The T16 frame geometry every 1440 signing board shares. */
async function t16Geometry(frame: Locator): Promise<void> {
  expect((await size(frame.locator("[data-signing='envelope-header']"))).height).toBe(46);
  expect((await size(frame.locator("[data-signing='documents']"))).width).toBe(240);
  expect((await size(frame.locator("[data-signing='well']"))).width).toBe(816);
  expect((await size(frame.locator("[data-signing='steps']"))).width).toBe(300);
  // 64 is a document row's minimum: a two-line title makes it 76, as the handoff draws it.
  for (const row of await frame.locator("[data-signing='documents'] [data-document]").all()) {
    expect((await size(row)).height).toBeGreaterThanOrEqual(64);
  }
}

async function tpl16(page: Page, st: string): Promise<Locator> {
  await openGallery(page, `screens/TPL-16?st=${st}`);
  const frame = page.locator(`[data-artboard='${st}'] [data-shell='app']`).first();
  await expect(frame).toBeVisible();
  return frame;
}

for (const st of ["t16b", "t16c"] as const) {
  test(`T16 ${st}: header 46, documents 240, well 816, steps 300, rows 64`, async ({ page }) => {
    await openGallery(page);
    const frame = specimen(
      page,
      "t16-signing-ceremony",
      `[data-artboard='${st}'] [data-shell='app']`,
    );
    await frame.first().scrollIntoViewIfNeeded();
    await t16Geometry(frame);
    expect((await size(frame.locator("[data-signing='page']"))).width).toBe(680);
  });
}

for (const st of ["b", "d", "f"] as const) {
  test(`TPL-16${st}: the T16 frame, the 680 page`, async ({ page }) => {
    const frame = await tpl16(page, st);
    await t16Geometry(frame);
    expect((await size(frame.locator("[data-signing='page']"))).width).toBe(680);
  });
}

test("TPL-16a: the provider's view fills the page's 680 in the 816 well", async ({ page }) => {
  const frame = await tpl16(page, "a");
  await t16Geometry(frame);
  expect((await size(frame.locator("[data-signing='provider-frame']"))).width).toBe(680);
});

test("TPL-16e: the T16 frame around the DF-11 card", async ({ page }) => {
  const frame = await tpl16(page, "e");
  await t16Geometry(frame);
});

test.describe("TPL-16g at 390", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  // The 44 × 44 targets (hit areas included) are F-06-T07's, in e2e/screens/TPL-16.spec.ts.
  test("the phone frame 390, the 64 sticky bar, its 48 primary", async ({ page }) => {
    const frame = await tpl16(page, "g");
    expect(await size(frame)).toEqual({ width: 390, height: 844 });
    const bar = frame.locator("[data-signing='mobile-sign-bar']");
    expect((await size(bar)).height).toBe(64);
    expect((await size(bar.locator("button"))).height).toBe(48);
  });
});

for (const st of ["a", "b", "c", "d", "e"] as const) {
  test(`TPL-01${st}: the 1400 × 860 window`, async ({ page }) => {
    await openGallery(page, `screens/TPL-01?st=${st}`);
    const frame = page.locator(`[data-artboard='tpl-01${st}'] [data-shell='app']`).first();
    expect(await size(frame)).toEqual({ width: 1400, height: 860 });
  });
}
