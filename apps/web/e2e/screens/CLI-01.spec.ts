// CLI-01 a–f in fixture mode (P-07-T12; build-screen-from-handoff §5): every scenario at 1440×900,
// DPR 2, from the /components gallery on fixtures (no API, no database), with axe at zero serious
// or critical findings. Tier C parity against the handoff PNGs is reported by the parity harness
// and locked in P-07-T63.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/CLI-01.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS = [
  { st: "a", ready: "184 clients" },
  { st: "b", ready: "Showing 25" },
  { st: "c", ready: "183 clients" },
  { st: "d", ready: "No clients match 'Schwab'." },
  { st: "e", ready: null },
  { st: "f", ready: "No clients yet." },
] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of ARTBOARDS) {
  test(`CLI-01${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/CLI-01?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    if (ready === null) {
      await expect(page.getByRole("status", { name: "Loading" })).toBeVisible();
    } else {
      await expect(page.getByText(ready)).toBeVisible();
    }
    if (st === "c") await expect(page.getByText("Ashford Manufacturing Co.")).toHaveCount(0);
    const { violations } = await new AxeBuilder({ page })
      .include(`[data-artboard='${st}']`)
      .analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}
