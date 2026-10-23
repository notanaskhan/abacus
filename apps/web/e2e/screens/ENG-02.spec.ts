// ENG-02 b, c, d, e and the prospect state in fixture mode (P-07-T20; build-screen-from-handoff
// §5): every scenario at 1440×900, DPR 2, from the /components gallery on fixtures, with axe at
// zero serious or critical findings. Tier C parity is reported by the parity harness (P-07-T63).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/ENG-02.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const STATES = [
  { st: "b", ready: "Blocked on a partner decision" },
  { st: "c", ready: "No work items yet." },
  { st: "d", ready: "Archive locked Jun 12, 2026 · WORM" },
  { st: "e", ready: null },
  { st: "prospect", ready: "Acceptance pending — Daniel Reyes" },
] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of STATES) {
  test(`ENG-02 ${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/ENG-02?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    if (ready === null) {
      await expect(page.getByRole("status", { name: "Loading" })).toBeVisible();
    } else {
      await expect(board.getByText(ready).first()).toBeVisible();
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
