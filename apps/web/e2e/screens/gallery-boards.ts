// A-08-T37 (TASK-8756): a screen's gallery artboards (`/components/screens/<ID>?st=`), each rendered
// with nothing busy and axe at zero serious or critical findings in the artboard and any overlay it
// opens, in light and in forced colors. A seeded violation fails it (gallery-boards.seed.spec.ts).
import AxeBuilder from "@axe-core/playwright";
import { type Page, expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

export async function seriousIn(page: Page, st: string): Promise<string[]> {
  let builder = new AxeBuilder({ page }).setLegacyMode(true).include(`[data-artboard='${st}']`);
  if ((await page.locator("[role='dialog']").count()) > 0)
    builder = builder.include("[role='dialog']");
  const { violations } = await builder.analyze();
  return violations
    .filter((v) => SERIOUS.has(v.impact ?? ""))
    .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
}

export function walkGallery(
  screen: string,
  states: readonly string[],
  options: { width?: 1440 | 390; loading?: readonly string[] } = {},
): void {
  const width = options.width ?? 1440;
  test.describe(`${screen} at ${String(width)}`, () => {
    test.use({
      viewport: { width, height: width === 390 ? 844 : 900 },
      deviceScaleFactor: 2,
      reducedMotion: "reduce",
    });
    for (const st of states) {
      test(`${screen}${st}: renders and axe finds nothing serious, forced colors too`, async ({
        page,
      }) => {
        await page.goto(
          `/components/screens/${screen}?st=${st}&frame=1${width === 390 ? "&w=390" : ""}`,
        );
        const board = page.locator(`[data-artboard='${st}']`);
        await expect(board).toBeVisible();
        if (options.loading?.includes(st) !== true) {
          await expect(board.locator("[aria-busy='true']")).toHaveCount(0);
        }
        expect(await seriousIn(page, st)).toEqual([]);
        await page.emulateMedia({ forcedColors: "active" });
        expect(await seriousIn(page, st)).toEqual([]);
      });
    }
  });
}
