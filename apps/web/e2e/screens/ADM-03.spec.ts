// ADM-03 a–h (G-01-T14; G-01-T16 screen spec) in fixture mode: every scenario at 1440×900, DPR 2,
// from the /components gallery on fixtures, each opening with its search (OPENS), with axe at zero
// serious or critical findings in the frame and in the overlay a state opens (b, c: the new wall
// sheet; g: the wall log). d is Remy Vidal in the offshore group, e Daniel Reyes (partner); h is
// the dirty Tax form, which the unit suite drives.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/ADM-03.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS: readonly { st: string; ready: string; overlay: string | null }[] = [
  { st: "a", ready: "46 seats · 224 returns", overlay: null },
  { st: "b", ready: "Block agent runs she starts on this client", overlay: "[role='dialog']" },
  {
    st: "c",
    ready: "Neil Ashcroft leads this relationship. Reassign the relationship partner first.",
    overlay: "[role='dialog']",
  },
  { st: "d", ready: "1 member", overlay: null },
  { st: "e", ready: "46 seats · 224 returns", overlay: null },
  { st: "f", ready: "Lena Park", overlay: null },
  { st: "g", ready: "Approved by Margaret Okonkwo", overlay: "[role='dialog']" },
  { st: "h", ready: "16 + 21 + 7 + 2 = 46 seats", overlay: null },
];

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready, overlay } of ARTBOARDS) {
  test(`ADM-03${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/ADM-03?st=${st}&frame=1`);
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
