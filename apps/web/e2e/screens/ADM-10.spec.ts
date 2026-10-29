// ADM-10 a, b, c, d, e, f, g (R-01-T32 screen spec) in fixture mode: every scenario at 1440×900, DPR 2,
// from the /components gallery on fixtures, with axe at zero serious or critical findings in the
// frame and in the overlay a state opens. The portal preview never shows the product's name.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/ADM-10.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const STATES: readonly string[] = ["a", "b", "c", "d", "e", "f", "g"];

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const st of STATES) {
  test(`ADM-10${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/ADM-10?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    await expect(board.locator("[aria-busy='true']")).toHaveCount(0);
    let builder = new AxeBuilder({ page }).include(`[data-artboard='${st}']`);
    if ((await page.locator("[role='dialog']").count()) > 0)
      builder = builder.include("[role='dialog']");
    const { violations } = await builder.analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}
