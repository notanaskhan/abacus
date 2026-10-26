// ADM-01 a–f (G-01-T07; G-01-T16 screen spec) in fixture mode: every scenario at 1440×900, DPR 2,
// from the /components gallery on fixtures (no API, no database), with axe at zero serious or
// critical findings. b, c and f are reached by editing a (the unit suite drives the edits), so
// their frames open clean; d is Daniel Reyes (partner), e Felix Andersen (security admin).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/ADM-01.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS: readonly { st: string; ready: string; overlay: string | null }[] = [
  { st: "a", ready: "46 of 46 seats · 0 pending invites", overlay: null },
  { st: "b", ready: "At a glance", overlay: null },
  { st: "c", ready: "At a glance", overlay: null },
  { st: "d", ready: "At a glance", overlay: null },
  { st: "e", ready: "At a glance", overlay: null },
  { st: "f", ready: "At a glance", overlay: null },
];

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready, overlay } of ARTBOARDS) {
  test(`ADM-01${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/ADM-01?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    await expect(page.getByText(ready).first()).toBeVisible();
    let builder = new AxeBuilder({ page }).include(`[data-artboard='${st}']`);
    if (overlay !== null) builder = builder.include(overlay);
    const { violations } = await builder.analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}
