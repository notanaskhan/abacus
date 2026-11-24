// AUD-38 a, b, c, d, e (T-06-T45) in fixture mode: every scenario at 1440×900, DPR 2,
// from the /components gallery on fixtures, with axe at zero serious or critical findings in the
// frame and in the overlay a state opens.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/AUD-38.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const STATES: readonly string[] = ["a", "b", "c", "d", "e"];

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const st of STATES) {
  test(`AUD-38${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/AUD-38?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    await expect(board.locator("[aria-busy='true']")).toHaveCount(0);
    // Legacy mode: the default multi-frame run never finishes on the template screens (its
    // results merge stalls; every rule alone completes), and the artboard has no frames to merge.
    let builder = new AxeBuilder({ page }).setLegacyMode(true).include(`[data-artboard='${st}']`);
    if ((await page.locator("[role='dialog']").count()) > 0)
      builder = builder.include("[role='dialog']");
    const { violations } = await builder.analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}
