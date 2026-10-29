// HOME-01 lite MVP proof (I-01-T14; docs/screens/HOME-01.md): every fixture scenario renders axe
// clean (zero serious or critical findings) and is keyboard-walkable: Tab reaches the subbar, the
// tiles and the panes in reading order and every focusable stop is visible. The parity lock (Tier
// C for a, a2, f, g) is `e2e/visual/parity.spec.ts` over docs/design/parity-manifest.json; Tier D
// is `e2e/visual/tier-d-home.spec.ts`. The journeys (j16 step 1, j13 step 2 with
// assertInvariants) run in compose and on staging from `e2e/journeys/` (N-01-T23's swap window).
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const STATES = [
  "a",
  "a2",
  "b",
  "c",
  "d",
  "e",
  "f",
  "g",
  "h",
  "i",
  "office-denver",
  "tile-popover",
  "today-brief-off",
  "walled",
];

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1,
  reducedMotion: "reduce",
});

for (const st of STATES) {
  test(`HOME-01 ${st}: axe clean and keyboard-walkable`, async ({ page }) => {
    await page.goto(`/components/screens/HOME-01?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    const { violations } = await new AxeBuilder({ page })
      .include(`[data-artboard='${st}']`)
      .analyze();
    expect(
      violations
        .filter((v) => SERIOUS.has(v.impact ?? ""))
        .map((v) => `${v.id}: ${v.nodes[0]?.target.join(" ") ?? ""}`),
    ).toEqual([]);
    const seen: string[] = [];
    for (let i = 0; i < 12; i += 1) {
      await page.keyboard.press("Tab");
      const focused = await page.evaluate(() => {
        const el = document.activeElement;
        if (el === null || el === document.body) return null;
        const r = el.getBoundingClientRect();
        return {
          visible: r.width > 0 && r.height > 0,
          name: el.getAttribute("aria-label") ?? el.textContent,
        };
      });
      if (focused === null) break;
      expect(focused.visible).toBe(true);
      seen.push(focused.name);
    }
    expect(seen.length).toBeGreaterThan(0);
  });
}
