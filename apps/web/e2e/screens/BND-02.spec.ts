// BND-02 a–f (P-06-T12) and g (P-06-T22; added to this spec by P-06-T26) in fixture mode
// (build-screen-from-handoff §5): every scenario at 1440×900, DPR 2, from the /components gallery
// on fixtures (no API, no database), with axe at zero serious or critical findings. Pixel parity
// against the handoff PNGs is P-06-T26's (Tier C), reported by e2e/parity/screens.spec.ts.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/BND-02.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS = [
  { st: "a", ready: "Published Feb 3 · 5 of 7 satisfied · 2 open" },
  { st: "b", ready: "Draft · 7 requests from the 2025 return" },
  { st: "c", ready: "Marked done by Claire Feld · Sep 15, 9:02 AM · 7 of 7" },
  { st: "d", ready: "3 overdue" },
  { st: "e", ready: "Not applicable this year" },
  { st: "f", ready: "Internal only — the client won't see this request." },
  { st: "g", ready: "Uploaded – needs review" },
] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of ARTBOARDS) {
  test(`BND-02${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/BND-02?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    await expect(board.getByText(ready).first()).toBeVisible();
    if (process.env.BND02_SHOTS !== undefined) {
      await board.screenshot({ path: `${process.env.BND02_SHOTS}/bnd02-${st}.png` });
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
