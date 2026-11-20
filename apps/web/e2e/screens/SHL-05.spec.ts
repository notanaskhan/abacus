// SHL-05 (G-04-T21 screen spec) in fixture mode: every artboard at 1440×900, DPR 2, from the
// /components gallery on fixtures, with axe at zero serious or critical findings in the frame and
// in any overlay the state opens; support sees no client content until a session is granted.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/SHL-05.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const STATES: readonly string[] = ["a", "b", "c", "d", "d2", "e", "f"];

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const st of STATES) {
  test(`SHL-05${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/SHL-05?st=${st}&frame=1`);
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

test("SHL-05c: the session reads Granted by Felix Andersen with Revoke", async ({ page }) => {
  await page.goto("/components/screens/SHL-05?st=c&frame=1");
  await expect(page.getByText(/Granted by Felix Andersen · until/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Revoke" })).toBeVisible();
});

test("SHL-05e: the CCH export reads Needs attention", async ({ page }) => {
  await page.goto("/components/screens/SHL-05?st=e&frame=1");
  await expect(page.getByText("Needs attention").first()).toBeVisible();
});
