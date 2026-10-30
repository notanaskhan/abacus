// INB-01 artboards (N-01-T28) in fixture mode, from the /components gallery at 1440×900, DPR 2: each
// renders and axe finds nothing serious or critical. Pixel parity (Tier C, the locks in
// docs/screens/INB-01.md) is reported by e2e/parity/screens.spec.ts; the list keyboard suite is below.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/INB-01.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const STATES = ["a", "b", "c", "d", "e", "f", "g"] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const st of STATES) {
  test(`INB-01${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/INB-01?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    const { violations } = await new AxeBuilder({ page })
      .include(`[data-artboard='${st}']`)
      .analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
    expect(serious).toEqual([]);
  });
}

// The list keyboard suite: no positive tabindex, and Tab reaches the thread rows' controls.
test("INB-01 list keyboard: Tab reaches the threads; no positive tabindex", async ({ page }) => {
  await page.goto("/components/screens/INB-01?st=a&frame=1");
  const board = page.locator("[data-artboard='a']");
  await expect(board).toBeVisible();
  expect(await board.locator("[tabindex]:not([tabindex='0']):not([tabindex='-1'])").count()).toBe(
    0,
  );
  const reached = new Set<string>();
  for (let i = 0; i < 40; i += 1) {
    await page.keyboard.press("Tab");
    const inside = await page.evaluate(
      () => document.activeElement?.closest("[data-artboard='a']") !== null,
    );
    if (inside)
      reached.add(await page.evaluate(() => document.activeElement?.outerHTML.slice(0, 80) ?? ""));
  }
  expect(reached.size).toBeGreaterThan(5);
});
