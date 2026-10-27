// ADM-07 a, b, c, e, f, g (G-02-T13; G-02-T21 screen spec) in fixture mode: every scenario at
// 1440×900, DPR 2, from the /components gallery on fixtures, each opening with its search (OPENS),
// with axe at zero serious or critical findings in the frame and the overlay a state opens (c: the
// event drawer). d (the dormant policy principal) is fixture-only and the unit suite's; the parity
// report measures the same artboards at Tier C.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/ADM-07.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS: readonly { st: string; ready: string; overlay: string | null }[] = [
  { st: "a", ready: "Showing 14 of 18,406", overlay: null },
  { st: "b", ready: "Showing 4 of 1,962", overlay: null },
  { st: "c", ready: "Immutable. Corrections are new events.", overlay: "[role='dialog']" },
  { st: "e", ready: "Showing 14 of 18,406", overlay: null },
  { st: "f", ready: "No events match 'pell street iii'.", overlay: null },
  { st: "g", ready: "Showing 14 of 18,406", overlay: null },
];

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready, overlay } of ARTBOARDS) {
  test(`ADM-07${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/ADM-07?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    await expect(page.getByText(ready).first()).toBeVisible();
    let builder = new AxeBuilder({ page }).include(`[data-artboard='${st}']`);
    if (overlay !== null) builder = builder.include(overlay);
    const { violations } = await builder.analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}
