// INB-02 artboards (N-01-T28) in fixture mode, from the /components gallery at 1440×900, DPR 2: each
// renders and axe finds nothing serious or critical. Pixel parity (Tier C, the locks in
// docs/screens/INB-02.md) is reported by e2e/parity/screens.spec.ts; the sheet keyboard suite is below.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/INB-02.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const STATES = ["a", "a2", "b", "c", "d", "e", "f", "g"] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const st of STATES) {
  test(`INB-02${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/INB-02?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    const { violations } = await new AxeBuilder({ page })
      .include(`[data-artboard='${st}']`)
      .analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
    expect(serious).toEqual([]);
  });
}

// The sheet keyboard suite: the sheet is a named dialog and focus starts inside it.
test("INB-02 sheet keyboard: a named dialog that holds focus", async ({ page }) => {
  await page.goto("/components/screens/INB-02?st=a&frame=1");
  const board = page.locator("[data-artboard='a']");
  await expect(board).toBeVisible();
  const dialog = board.getByRole("dialog").first();
  await expect(dialog).toBeVisible();
  expect(
    (await dialog.getAttribute("aria-label")) ?? (await dialog.getAttribute("aria-labelledby")),
  ).toBeTruthy();
  await page.keyboard.press("Tab");
  expect(
    await page.evaluate(() => document.activeElement?.closest("[role='dialog']") !== null),
  ).toBe(true);
});
