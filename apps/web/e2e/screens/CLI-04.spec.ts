// CLI-04 a–g in fixture mode (P-07-T33; build-screen-from-handoff §5): every scenario at
// 1440×900, DPR 2, from the /components gallery on fixtures (no API, no database), with axe at zero
// serious or critical findings. Tier C parity against the handoff PNGs is reported by the parity
// harness and locked in P-07-T63 (mask d's sub-line, DF-24).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/CLI-04.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS = [
  { st: "a", ready: "3 active · 1 invited · 2 not invited" },
  { st: "b", ready: "Invite to portal" },
  { st: "c", ready: "3 active · 2 invited · 1 not invited" },
  { st: "d", ready: "3 incorrect codes" },
  { st: "e", ready: "Change access — Sam Ortiz" },
  { st: "f", ready: "Revoke portal access for Summit Plan Administrators?" },
  { st: "g", ready: "Non-attest client: no SKE designation required" },
] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of ARTBOARDS) {
  test(`CLI-04${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/CLI-04?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    await expect(page.getByText(ready)).toBeVisible();
    const { violations } = await new AxeBuilder({ page }).analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}
