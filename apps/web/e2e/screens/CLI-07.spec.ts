// CLI-07 a–g in fixture mode (P-07-T46; build-screen-from-handoff §5): every scenario at
// 1440×900, DPR 2, from the /components gallery on fixtures, with axe at zero serious or critical
// findings. Tier C parity is reported by the parity harness.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/CLI-07.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const STATES = [
  { st: "a", ready: "Form 706 is required" },
  { st: "b", ready: "Not ready for decision — 1 manual check open" },
  { st: "c", ready: "Accrued Agent is screening · 4 of 9 sections" },
  { st: "d", ready: "Draft engagement letter →" },
  { st: "e", ready: "Open Estate of Walter Thornbury" },
  { st: "f", ready: "Prior-year history — one open item" },
  { st: "g", ready: "Client responsiveness is below the firm rate" },
] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of STATES) {
  test(`CLI-07 ${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/CLI-07?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    await expect(page.getByText(ready).first()).toBeVisible();
    const { violations } = await new AxeBuilder({ page }).analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}
