// ADM-02 a–g (G-01-T10; G-01-T16 screen spec) in fixture mode: every scenario at 1440×900, DPR 2,
// from the /components gallery on fixtures, each opening with its search (OPENS), with axe at zero
// serious or critical findings in the frame and in the overlay a state opens (c: Invite user;
// d: Lena Park). e is the Nov 2 snapshot after the seasonal job; f the pending invite on Jan 5.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/ADM-02.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS: readonly { st: string; ready: string; overlay: string | null }[] = [
  { st: "a", ready: "SSO + MFA 46 of 46", overlay: null },
  { st: "b", ready: "Sign-off L4, release, final approval", overlay: null },
  {
    st: "c",
    ready: "All 46 seats are assigned. Add seats or deactivate a user first.",
    overlay: "[role='dialog']",
  },
  { st: "d", ready: "Oct 31, 2026", overlay: "[role='dialog']" },
  { st: "e", ready: "5 · access ended Oct 31", overlay: null },
  { st: "f", ready: "Invite pending · expires Jan 19", overlay: null },
  { st: "g", ready: "0 confirmed · 46 not yet · 0 declined", overlay: null },
];

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready, overlay } of ARTBOARDS) {
  test(`ADM-02${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/ADM-02?st=${st}&frame=1`);
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
