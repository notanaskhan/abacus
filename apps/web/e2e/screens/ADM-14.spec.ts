// ADM-14 (G-04-T21 screen spec) in fixture mode: every artboard at 1440×900, DPR 2, from the
// /components gallery on fixtures, with axe at zero serious or critical findings in the frame and
// in any overlay the state opens; figures are the server's integers.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/ADM-14.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const STATES: readonly string[] = ["a", "b", "c", "d", "e", "f"];

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const st of STATES) {
  test(`ADM-14${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/ADM-14?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    await expect(board.locator("[aria-busy='true']")).toHaveCount(0);
    let builder = new AxeBuilder({ page }).setLegacyMode(true).include(`[data-artboard='${st}']`);
    if ((await page.locator("[role='dialog']").count()) > 0)
      builder = builder.include("[role='dialog']");
    const { violations } = await builder.analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}

test("ADM-14a: within plan, 14,920 of 20,000 included", async ({ page }) => {
  await page.goto("/components/screens/ADM-14?st=a&frame=1");
  await expect(
    page
      .locator("[data-artboard='a']")
      .getByText(/14,920/)
      .first(),
  ).toBeVisible();
  await expect(page.locator("[data-artboard='a']").getByText("of 20,000 included")).toBeVisible();
});

test("ADM-14e: a partner reads it with every band locked", async ({ page }) => {
  await page.goto("/components/screens/ADM-14?st=e&frame=1");
  await expect(
    page.getByText("Only firm admins can change alerts and billing contact."),
  ).toBeVisible();
});
