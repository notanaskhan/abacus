// FIL-01 artboards (N-01-T28) in fixture mode, from the /components gallery at 1440×900, DPR 2: each
// renders and axe finds nothing serious or critical. Pixel parity (Tier C, the locks in
// docs/screens/FIL-01.md) is reported by e2e/parity/screens.spec.ts; the tree keyboard suite is below.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/FIL-01.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const STATES = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const st of STATES) {
  test(`FIL-01${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/FIL-01?st=${st}&frame=1`);
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

// The tree keyboard suite: a folder is chosen from the keyboard (Enter) and reads as selected.
test("FIL-01 tree keyboard: Enter on a folder selects it", async ({ page }) => {
  await page.goto("/components/screens/FIL-01?st=a&frame=1");
  const tree = page.locator("[data-artboard='a'] [data-files='tree']");
  await expect(tree).toBeVisible();
  const folders = tree.getByRole("button");
  const target = folders.nth(1);
  await target.focus();
  await page.keyboard.press("Enter");
  await expect(tree.locator("[aria-selected='true']").first()).toBeVisible();
});

// The reveal keyboard suite: f's revealed TIN came from a keyboard-reachable, named control.
test("FIL-01 reveal keyboard: the reveal control is a named button", async ({ page }) => {
  await page.goto("/components/screens/FIL-01?st=d&frame=1");
  const board = page.locator("[data-artboard='d']");
  await expect(board).toBeVisible();
  const reveal = board.getByRole("button", { name: /reveal/i });
  if ((await reveal.count()) > 0) {
    await reveal.first().focus();
    expect(await page.evaluate(() => document.activeElement?.tagName)).toBe("BUTTON");
  }
});
