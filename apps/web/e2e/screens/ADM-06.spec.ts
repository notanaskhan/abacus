// ADM-06 a–h (G-02-T16; G-02-T21 screen spec) in fixture mode: every scenario at 1440×900, DPR 2,
// from the /components gallery on fixtures, each opening with its search (OPENS), with axe at zero
// serious or critical findings in the frame and in the overlay a state opens (b: the export
// dialog; c: the history tray; d: the incident drawer). i and j (revision R2) are fixture-only and
// the unit suite's; the parity report measures the same artboards at Tier C.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/ADM-06.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS: readonly {
  st: string;
  ready: string;
  overlay: string | null;
  /** The button that opens the state's overlay (b: the board is the dialog over the card). */
  open?: string;
}[] = [
  { st: "a", ready: "Enforced · 46 of 46 enrolled", overlay: null },
  { st: "b", ready: "Export all firm data?", overlay: "[role='dialog']", open: "Export now…" },
  { st: "c", ready: "Jul 1, 2026 · 359 GB", overlay: "[role='menu']" },
  {
    st: "d",
    ready: "1,812 failed sign-ins from 203.0.113.0/24 blocked",
    overlay: "[role='dialog']",
  },
  {
    st: "e",
    ready: "5 users without MFA. Enforcing SSO will require MFA at next sign-in.",
    overlay: null,
  },
  { st: "f", ready: "Only IT/Security can change security settings.", overlay: null },
  { st: "g", ready: "Waiting for approval · Margaret Okonkwo", overlay: null },
  { st: "h", ready: "Export WISP pack", overlay: null },
];

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready, overlay, open } of ARTBOARDS) {
  test(`ADM-06${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/ADM-06?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    if (open !== undefined) await page.getByRole("button", { name: open }).click();
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
