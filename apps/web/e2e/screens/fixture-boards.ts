// Screens that aren't in the /components gallery walk their artboards through the real route on
// fixtures (`?screen=<ID>&st=<state>`, DEC-457): each renders and axe finds nothing serious.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

export interface Board {
  st: string;
  ready: string;
}

export function walkBoards(screen: string, path: string, boards: readonly Board[]): void {
  test.use({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
    reducedMotion: "reduce",
  });
  for (const { st, ready } of boards) {
    test(`${screen}${st}: renders and axe finds nothing serious`, async ({ page }) => {
      await page.goto(`${path}?screen=${screen}&st=${st}`);
      await expect(page.locator(`[data-screen='${screen}']`).first()).toBeVisible();
      await expect(page.getByText(ready).first()).toBeVisible();
      const { violations } = await new AxeBuilder({ page }).analyze();
      const serious = violations
        .filter((v) => SERIOUS.has(v.impact ?? ""))
        .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
      expect(serious).toEqual([]);
    });
  }
}
