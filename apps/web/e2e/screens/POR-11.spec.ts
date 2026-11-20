// POR-11 (C-01-T50 screen spec): Copperleaf's close requests and transaction questions in the
// portal, a to c at 1400 and a at 390, from the /components gallery on fixtures, with axe at zero
// serious or critical findings in light and forced colors, and no firm-only word or field on the
// client's page (the portal never shows the firm's workflow states).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/POR-11.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { type Page, expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const FIRM_ONLY = [
  "Pending incorporation",
  "Matched to uploaded document",
  "Visible to client",
  "Accrued",
];

test.use({ deviceScaleFactor: 2, reducedMotion: "reduce" });

async function serious(page: Page, st: string): Promise<string[]> {
  let builder = new AxeBuilder({ page }).setLegacyMode(true).include(`[data-artboard='${st}']`);
  if ((await page.locator("[role='dialog']").count()) > 0)
    builder = builder.include("[role='dialog']");
  const { violations } = await builder.analyze();
  return violations
    .filter((v) => SERIOUS.has(v.impact ?? ""))
    .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
}

for (const [st, width] of [
  ["a", 1400],
  ["b", 1400],
  ["c", 1400],
  ["a", 390],
] as const) {
  test(`POR-11${st} at ${String(width)}: renders, axe finds nothing serious, no firm-only word`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await page.goto(`/components/screens/POR-11?st=${st}&frame=1${width === 390 ? "&w=390" : ""}`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    await expect(board.locator("[aria-busy='true']")).toHaveCount(0);
    const text = (await board.textContent()) ?? "";
    for (const word of FIRM_ONLY) expect(text).not.toContain(word);
    expect(await serious(page, st)).toEqual([]);
    await page.emulateMedia({ forcedColors: "active" });
    expect(await serious(page, st)).toEqual([]);
  });
}
