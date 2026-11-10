// Tier D for SHL-13 and WB-09 (P-09-T18; P-09 §5.4): computed geometry and type, not pixels, so it
// needs no baseline and blocks wherever the visual project runs. The dock pane 330 × 733 radius 12,
// header 46 with "Agent" at 14.5/500, the composer a 38-high pill on nested, the user bubble radius
// 14; the drawer 480 at top/right/bottom 10, radius 14, header 46, Segmented 28.
import { type Locator, type Page, expect, test } from "@playwright/test";

test.use({
  viewport: { width: 1440, height: 1700 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

async function open(page: Page, screen: string, st: string): Promise<void> {
  await page.goto(`/components/screens/${screen}?st=${st}&frame=1&static=1`);
  await expect(page.locator(`[data-artboard='${st}']`)).toBeVisible();
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

function style(target: Locator, prop: string): Promise<string> {
  return target.evaluate((el, p) => getComputedStyle(el).getPropertyValue(p), prop);
}

for (const n of [1, 2, 3, 4, 5, 6, 7, 8]) {
  test(`SHL-13 dock ${String(n)}: 330 × 733, radius 12, header 46 with Agent at 14.5/500`, async ({
    page,
  }) => {
    await open(page, "SHL-13", "board");
    const dock = page.locator(`[data-dock='${String(n)}']`);
    await expect(dock.locator("[data-run-pane]")).toBeVisible();
    const { w, h } = await box(dock);
    expect(w).toBe(330);
    expect(h).toBe(733);
    expect(await style(dock, "border-top-left-radius")).toBe("12px");
    const header = dock.locator("[data-run-pane] > header").first();
    expect((await box(header)).h).toBe(46);
    const title = header.getByRole("heading", { name: "Agent" });
    expect(await style(title, "font-size")).toBe("14.5px");
    expect(await style(title, "font-weight")).toBe("500");
    const composer = dock.getByRole("form", { name: "Message the agent" });
    if ((await composer.count()) > 0) {
      expect((await box(composer)).h).toBe(38);
      expect(await style(composer, "background-color")).toBe("rgb(239, 238, 235)");
    }
  });
}

test("SHL-13 dock 2: the user bubble is radius 14", async ({ page }) => {
  await open(page, "SHL-13", "board");
  const bubble = page.locator("[data-dock='2'] li.ml-auto").first();
  await expect(bubble).toBeVisible();
  expect(await style(bubble, "border-top-left-radius")).toBe("14px");
});

for (const st of ["a", "b", "c", "d"] as const) {
  test(`WB-09${st}: drawer 480 at top/right/bottom 10, radius 14, header 46, Segmented 28`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await open(page, "WB-09", st);
    const drawer = page.getByRole("dialog").last();
    await expect(drawer).toBeVisible();
    const { x, y, w, h } = await box(drawer);
    expect(w).toBe(480);
    expect(y).toBe(10);
    expect(1440 - (x + w)).toBe(10);
    expect(900 - (y + h)).toBe(10);
    expect(await style(drawer, "border-top-left-radius")).toBe("14px");
    expect((await box(drawer.locator("header").first())).h).toBe(46);
    const tabs = drawer.getByRole("tablist");
    if ((await tabs.count()) > 0) expect((await box(tabs.first())).h).toBe(28);
  });
}
