// Tier D for the A-07 canvases (A-07-T48; A-07 §5.4): computed geometry, not pixels. T2 record
// cockpit (AUD-24, AUD-25): rail 330 · canvas 696 · dock 330. T10 document on well (AUD-22,
// AUD-23): structure 470 · paper pane 896. Blocking wherever the visual project runs.
import { type Page, expect, test } from "@playwright/test";

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

async function widths(page: Page, screen: string, st: string): Promise<number[]> {
  await page.goto(`/components/screens/${screen}?st=${st}&frame=1&static=1`);
  const root = page.locator(`[data-artboard='${st}'] [data-screen='${screen}']`);
  await expect(root).toBeVisible();
  return root.evaluate((el) =>
    Array.from(el.querySelectorAll<HTMLElement>(":scope > *, :scope > * > *"), (c) =>
      Math.round(c.getBoundingClientRect().width),
    ),
  );
}

for (const [screen, st] of [
  ["AUD-24", "a"],
  ["AUD-25", "a"],
] as const) {
  test(`${screen}${st}: T2 rail 330, canvas 696, dock 330`, async ({ page }) => {
    const found = await widths(page, screen, st);
    expect(found).toContain(330);
    expect(found).toContain(696);
    expect(found.filter((w) => w === 330).length).toBeGreaterThanOrEqual(2);
  });
}

for (const [screen, st] of [
  ["AUD-22", "a"],
  ["AUD-23", "a"],
] as const) {
  test(`${screen}${st}: T10 structure 470, paper pane 896`, async ({ page }) => {
    const found = await widths(page, screen, st);
    expect(found).toContain(470);
    expect(found).toContain(896);
  });
}
