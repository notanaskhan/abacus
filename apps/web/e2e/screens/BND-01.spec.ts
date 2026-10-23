// BND-01 a, c, d, e in fixture mode (P-06-T09; build-screen-from-handoff §5): every scenario at
// 1440×900, DPR 2, from the /components gallery on fixtures (no API, no database), with axe at zero
// serious or critical findings. Pixel parity against the handoff PNGs is P-06-T26's (Tier C).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/BND-01.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS = [
  { st: "a", ready: "Showing 15 of 241" },
  { st: "c", ready: "Showing 16 of 241" },
  { st: "d", ready: "No TY2026 binders yet." },
  { st: "e", ready: null },
] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of ARTBOARDS) {
  test(`BND-01${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/BND-01?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    if (ready === null) {
      await expect(page.getByRole("status", { name: "Loading" })).toBeVisible();
    } else {
      await expect(page.getByText(ready)).toBeVisible();
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
