// HOME-02 proof (I-01-T22; docs/screens/HOME-02.md): every artboard renders axe clean (zero serious
// or critical findings) and the queue is keyboard-walkable: J and K move the selection, and Tab
// stops are visible. The parity lock (Tier C for a, c, d, e, f, g) is `e2e/visual/parity.spec.ts`
// over docs/design/parity-manifest.json; Tier D is `e2e/visual/tier-d-home.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const STATES = ["a", "b", "c", "d", "e", "f", "g"];

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1,
  reducedMotion: "reduce",
});

for (const st of STATES) {
  test(`HOME-02 ${st}: axe clean and keyboard-walkable`, async ({ page }) => {
    await page.goto(`/components/screens/HOME-02?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    await expect(board.locator("[data-home02='subbar']")).toBeVisible();
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

test("HOME-02 a: J moves the selection down the queue and K moves it back", async ({ page }) => {
  await page.goto("/components/screens/HOME-02?st=a&frame=1");
  const queue = page.locator("[data-artboard='a'] [data-home02='queue']");
  await expect(queue).toBeVisible();
  const current = queue.locator("[aria-current='true']");
  const first = await current.first().textContent();
  await current.first().focus();
  await page.keyboard.press("j");
  await expect(current.first()).not.toHaveText(first ?? "");
  await page.keyboard.press("k");
  await expect(current.first()).toHaveText(first ?? "");
});
