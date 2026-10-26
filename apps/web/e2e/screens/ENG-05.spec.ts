// ENG-05 a–e in fixture mode (P-07-T39; build-screen-from-handoff §5): every scenario at
// 1440×900, DPR 2, from the /components gallery on fixtures, with axe at zero serious or critical
// findings. Tier C parity is reported by the parity harness (P-07-T63).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/ENG-05.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const STATES = [
  { st: "a", ready: "5 of 6 confirmed" },
  { st: "b", ready: "Assignment pending independence" },
  { st: "c", ready: "Replace EQR reviewer" },
  { st: "d", ready: "6 of 6 confirmed" },
  { st: "e", ready: "No team yet." },
] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of STATES) {
  test(`ENG-05 ${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/ENG-05?st=${st}&frame=1`);
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
