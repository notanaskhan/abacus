// POR-13 a–f (T-02-T27) in fixture mode: every scenario at 1440×900, DPR 2, from the
// /components gallery on fixtures, with axe at zero serious or critical findings in the frame.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/POR-13.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS: readonly { st: string; ready: string }[] = [
  { st: "a", ready: "160,000" },
  { st: "b", ready: "Not released yet" },
  { st: "c", ready: "400,270" },
  { st: "d", ready: "Upload a signed Form W-9" },
  { st: "e", ready: "Superseded (amended K-1)" },
  { st: "f", ready: "Your K-1s are in Deliverables › My K-1s" },
];

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of ARTBOARDS) {
  test(`POR-13${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/POR-13?st=${st}&frame=1`);
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
