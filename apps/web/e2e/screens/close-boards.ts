// C-01-T50 (TASK-8755): the close screens walk their artboards on their live routes in fixture
// mode (`?screen=<ID>&st=<state>`; the route's `_closeId_`, `_accountRef_` and `_clientId_` resolve
// to the state's records, screen-scenarios.ts), at 1440×900, DPR 2, motion reduced. Each renders
// with nothing busy, and axe finds nothing serious or critical in the page and in any overlay the
// state opens, in light and in forced colors.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
export const CLOSES = ["closes.engine"];

async function serious(page: import("@playwright/test").Page): Promise<string[]> {
  const { violations } = await new AxeBuilder({ page }).setLegacyMode(true).analyze();
  return violations
    .filter((v) => SERIOUS.has(v.impact ?? ""))
    .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
}

export function walkClose(
  screen: string,
  path: string,
  states: readonly string[],
  flags: readonly string[] = CLOSES,
  /** Designed loading states (the C-20 skeleton): busy is what they show. */
  loading: readonly string[] = [],
): void {
  test.use({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
    reducedMotion: "reduce",
  });
  const on = flags.length === 0 ? "" : `&flags=${flags.join(",")}`;
  for (const st of states) {
    test(`${screen} ${st}: renders and axe finds nothing serious, forced colors too`, async ({
      page,
    }) => {
      await page.goto(`${path}?screen=${screen}&st=${st}${on}`);
      const body = page.locator(`[data-screen='${screen}'], [data-screen-body='${screen}']`);
      await expect(body.first()).toBeVisible();
      if (loading.includes(st))
        await expect(page.locator("[aria-busy='true']").first()).toBeVisible();
      else await expect(page.locator("[aria-busy='true']")).toHaveCount(0);
      expect(await serious(page)).toEqual([]);
      await page.emulateMedia({ forcedColors: "active" });
      expect(await serious(page)).toEqual([]);
    });
  }
}
