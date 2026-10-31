// T-02-T32: the six T-02 screens (TAX-01, TAX-02, TAX-03, TXP-12, POR-05, POR-13) at 1400 and 390
// wide, every artboard, from the /components gallery on fixtures, with axe at zero serious or
// critical findings in the frame. Portal screens never show the product's name (INV-4).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/t02-screens-widths.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const SCREENS: Readonly<Record<string, readonly string[]>> = {
  "TAX-01": ["a", "b", "c", "d", "e", "f", "g"],
  "TAX-02": ["a", "b", "c", "d", "e"],
  "TAX-03": ["a", "a2", "b", "c", "d", "e", "f"],
  "TXP-12": ["a", "a2", "a3", "a4", "a5", "b", "b2", "c", "d", "e", "f"],
  "POR-05": ["a", "b", "c", "d", "e", "f"],
  "POR-13": ["a", "b", "c", "d", "e", "f"],
};
const WIDTHS = [1400, 390] as const;

test.use({ deviceScaleFactor: 2, reducedMotion: "reduce" });

for (const width of WIDTHS) {
  for (const [id, states] of Object.entries(SCREENS)) {
    for (const st of states) {
      test(`${id}${st} at ${String(width)}: renders and axe finds nothing serious`, async ({
        page,
      }) => {
        await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
        await page.goto(`/components/screens/${id}?st=${st}&frame=1&w=${String(width)}`);
        const board = page.locator(`[data-artboard='${st}']`);
        await expect(board).toBeVisible();
        await expect(board.locator("[aria-busy='true']")).toHaveCount(0);
        if (id.startsWith("POR-")) expect(await board.innerText()).not.toMatch(/Accrued/);
        const { violations } = await new AxeBuilder({ page })
          .include(`[data-artboard='${st}']`)
          .analyze();
        const serious = violations
          .filter((v) => SERIOUS.has(v.impact ?? ""))
          .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
        expect(serious).toEqual([]);
      });
    }
  }
}
