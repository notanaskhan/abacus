// Screens that aren't in the /components gallery walk their artboards through the real route on
// fixtures (`?screen=<ID>&st=<state>`, DEC-457): each renders and axe finds nothing serious.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

export interface Board {
  st: string;
  ready: string;
  /** More of the state's own search (`tab=activity`). */
  search?: string;
}

/** `flags`: what E0 leaves off and the screen's route needs on (`?flags=`, fixture project only). */
export function walkBoards(
  screen: string,
  path: string,
  boards: readonly Board[],
  flags: readonly string[] = [],
): void {
  test.use({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
    reducedMotion: "reduce",
  });
  const on = flags.length === 0 ? "" : `&flags=${flags.join(",")}`;
  for (const { st, ready, search } of boards) {
    test(`${screen}${st}: renders and axe finds nothing serious`, async ({ page }) => {
      const more = search === undefined ? "" : `&${search}`;
      await page.goto(`${path}?screen=${screen}&st=${st}${on}${more}`);
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
