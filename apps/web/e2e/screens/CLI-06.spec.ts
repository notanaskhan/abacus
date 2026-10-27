// CLI-06 a–f, h and i in fixture mode (P-07-T49; g is P-07-T54): every scenario at 1440×900,
// DPR 2, from the /components gallery on fixtures, with axe at zero serious or critical findings.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/CLI-06.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const STATES = [
  { st: "a", ready: "No conflicts" },
  { st: "b", ready: "96% match · Walter Thornbury" },
  { st: "c", ready: "Disclosure to a fiduciary is permitted under §301.7216-2(j)." },
  { st: "d", ready: "Contact" },
  { st: "e", ready: "Form 706" },
  { st: "f", ready: "Create & start acceptance" },
  { st: "h", ready: "Harborline Trust Company" },
  { st: "i", ready: "Required for Form 706 due date" },
] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of STATES) {
  test(`CLI-06 ${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/CLI-06?st=${st}&frame=1`);
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
