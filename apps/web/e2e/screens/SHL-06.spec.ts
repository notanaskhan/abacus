// SHL-06 g and the sign-in error states in fixture mode (P-01-T11; build-screen-from-handoff §5):
// every scenario at 1440×900, DPR 2, from the /components gallery on fixtures (no API, no
// database), with axe at zero serious or critical findings. Tier C parity for g is the parity
// harness's `shl-06g.window` entry (docs/design/parity-manifest.json).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/SHL-06.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS = [
  { st: "g", ready: "Signing in…" },
  { st: "error", ready: "Sign-in didn't complete" },
  { st: "expired", ready: "Your session ended. Sign in again to carry on." },
] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of ARTBOARDS) {
  test(`SHL-06 ${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/SHL-06?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    await expect(board.getByText(ready).first()).toBeVisible();
    await expect(board.locator("input[type=password]")).toHaveCount(0);
    const { violations } = await new AxeBuilder({ page })
      .include(`[data-artboard='${st}']`)
      .analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}
