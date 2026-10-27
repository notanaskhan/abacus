// CLI-08 a–g and the declined-note state in fixture mode (P-07-T48): every scenario at 1440×900,
// DPR 2, from the /components gallery on fixtures, with axe at zero serious or critical findings.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/CLI-08.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const STATES = [
  { st: "a", ready: "4 of 5 confirmed" },
  { st: "b", ready: "Permitted — management takes responsibility" },
  { st: "c", ready: "Harborline Trust Company" },
  { st: "d", ready: "Years served" },
  { st: "e", ready: "I am not a participant in the plan." },
  { st: "f", ready: "5 of 5 confirmed" },
  { st: "g", ready: "Breach logged — evaluate, communicate to TCWG, remediate" },
  { st: "declined", ready: "Declined" },
] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of STATES) {
  test(`CLI-08 ${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/CLI-08?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    await expect(page.getByText(ready).first()).toBeVisible();
    const { violations } = await new AxeBuilder({ page }).analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}
