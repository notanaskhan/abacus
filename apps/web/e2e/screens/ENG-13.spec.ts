// ENG-13 a–e in fixture mode (P-07-T60; build-screen-from-handoff §5): every scenario at
// 1440×900, DPR 2, from the /components gallery on fixtures, with axe at zero serious or critical
// findings. Tier C parity is reported by the parity harness (P-07-T63).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/ENG-13.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const STATES = [
  { st: "a", ready: "Learned context · 3" },
  { st: "b", ready: "Nothing to reconcile." },
  { st: "c", ready: "Signed-off FY2026 work is never changed." },
  { st: "d", ready: "The archive is locked; its evidence is referenced read-only." },
  { st: "e", ready: "Create & draft letter" },
] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of STATES) {
  test(`ENG-13 ${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/ENG-13?st=${st}&frame=1`);
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
