// KNW-04 a–i, j and the C-20 conditions (K-02-T19; K-02 §10 item 1) in fixture mode: every scenario
// at 1440×900, DPR 2, from the /components gallery on fixtures, with axe at zero serious or critical
// findings. Pixel parity against the handoff PNGs is the parity report's (Tier C,
// e2e/parity/screens.spec.ts) once KNW-04's manifest leaves `planned` (DEC-195).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/KNW-04.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS = [
  { st: "a", ready: "BH AJE thresholds v2" },
  { st: "b", ready: "Apply to returns…" },
  { st: "c", ready: "Review levels" },
  { st: "d", ready: "BH-TAX-02" },
  { st: "e", ready: "Variance thresholds" },
  { st: "f", ready: "Materiality ranges" },
  { st: "g", ready: "Document confidence" },
  { st: "h", ready: "SSARS & CAS" },
  { st: "i", ready: "Draft v3" },
  { st: "j", ready: "Federal due-date rules · TY2025" },
  { st: "draft_hidden", ready: "Review checklists" },
  { st: "no_examples", ready: "No examples yet" },
  { st: "flag_off", ready: null },
] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of ARTBOARDS) {
  test(`KNW-04 ${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/KNW-04?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    if (ready === null) {
      await expect(page.locator("[data-flag-off='knowledge.firm_standards']")).toBeVisible();
    } else {
      await expect(page.getByText(ready).first()).toBeVisible();
    }
    const { violations } = await new AxeBuilder({ page })
      .include(`[data-artboard='${st}']`)
      .analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}
