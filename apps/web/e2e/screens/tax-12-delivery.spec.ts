// TAX-12 delivery and e-file (T-01-T46) in fixture mode: every artboard at 1400×900, DPR 2, from the /components
// gallery on fixtures, with axe at zero serious or critical findings in the frame.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/tax-12-delivery.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const STATES: readonly string[] = ["a", "a2", "b", "c", "c2", "d", "e"];

test.use({
  viewport: { width: 1400, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const st of STATES) {
  test(`TAX-12${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/TAX-12?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    await expect(board.locator("[aria-busy='true']")).toHaveCount(0);
    const { violations } = await new AxeBuilder({ page })
      .include(`[data-artboard='${st}']`)
      .analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}
