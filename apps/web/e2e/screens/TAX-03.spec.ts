// TAX-03 a, a2, b–f (T-02-T19) in fixture mode: every scenario at 1440×900, DPR 2, from the
// /components gallery on fixtures, with axe at zero serious or critical findings in the frame.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/TAX-03.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS: readonly { st: string; ready: string }[] = [
  { st: "a", ready: "5 of 7 requests satisfied" },
  { st: "a2", ready: "Approve Document" },
  { st: "b", ready: "6 of 7 requests satisfied" },
  { st: "c", ready: "7 of 7 requests satisfied" },
  { st: "d", ready: "Released Sep 15" },
  { st: "e", ready: "Duplicate · same hash" },
  { st: "f", ready: "No requests yet." },
];

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of ARTBOARDS) {
  test(`TAX-03${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/TAX-03?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    await expect(page.getByText(ready).first()).toBeVisible();
    const { violations } = await new AxeBuilder({ page })
      .include(`[data-artboard='${st}']`)
      .analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}
