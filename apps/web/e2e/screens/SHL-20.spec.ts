// SHL-20 a–f (P-06-T22) in fixture mode (build-screen-from-handoff §5; spec added by P-06-T26):
// every scenario at 1440×900, DPR 2, from the /components gallery on fixtures (no API, no
// database), with axe at zero serious or critical findings in the frame and in the overlay the
// artboard opens (b: the O3 follow-up sheet; f: the "Why?" popover). Tier C parity is reported by
// the parity harness (e2e/parity/screens.spec.ts).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/SHL-20.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const STATES = [
  { st: "a", ready: "Flagged", overlay: null },
  { st: "b", ready: "Send to Luis Ferrante", overlay: "[role='dialog']" },
  { st: "c", ready: "Screening 2 new files…", overlay: null },
  { st: "d", ready: "40 of 40 payments supported", overlay: null },
  { st: "e", ready: "Not screened", overlay: null },
  { st: "f", ready: "Send feedback", overlay: "[role='dialog']" },
] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready, overlay } of STATES) {
  test(`SHL-20${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/SHL-20?st=${st}&frame=1`);
    await expect(page.locator(`[data-state='${st}'] [data-screen='SHL-20']`)).toBeVisible();
    await expect(page.getByText(ready).first()).toBeVisible();
    let builder = new AxeBuilder({ page }).include(`[data-state='${st}']`);
    if (overlay !== null) builder = builder.include(overlay);
    const { violations } = await builder.analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}
