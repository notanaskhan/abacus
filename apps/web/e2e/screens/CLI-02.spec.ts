// CLI-02 a, a2, b, c, e, f in fixture mode (P-07-T19; build-screen-from-handoff §5): every
// scenario at 1440×900, DPR 2, from the /components gallery on fixtures (no API, no database),
// with axe at zero serious or critical findings. Tier C parity against the handoff PNGs is
// reported by the parity harness and locked in P-07-T63.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/CLI-02.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS = [
  { st: "a", ready: "K-1 packages · TY2025" },
  { st: "a2", ready: "owen.calder@ridgelinepp.com" },
  { st: "b", ready: "•••-••-2208 (Claire)" },
  { st: "c", ready: "11 of 24" },
  { st: "e", ready: "No engagements yet." },
  { st: "f", ready: "Client responsiveness" },
] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of ARTBOARDS) {
  test(`CLI-02${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/CLI-02?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    await expect(board.getByText(ready).first()).toBeVisible();
    const { violations } = await new AxeBuilder({ page })
      .include(`[data-artboard='${st}']`)
      .analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}
