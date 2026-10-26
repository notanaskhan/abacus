// POR-04 a–g in fixture mode (R-01-T12, R-01-T21; portal-screen): every request-sheet artboard at
// 1400 and on the 390 preset, from the /components gallery on fixtures, with axe at zero serious or
// critical findings, no "Accrued" in the text or in any attribute a person or assistive technology
// meets, and at most one primary button (the contract's AVOID line). e and f are fixture-only (the
// question and decision slots, C-01 and T-06 / T-09). Parity is R-01-T31's.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/POR-04.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS = [
  { st: "a", ready: "To do · requested Feb 3" },
  { st: "b", ready: "Mark not applicable" },
  { st: "c", ready: "✓ Received by email Sep 14" },
  { st: "d", ready: "Returned · wrong year" },
  { st: "e", ready: "What was the $3,200 payment to Sound Electric?" },
  { st: "f", ready: "Answer by 5:00 PM CT today" },
  { st: "g", ready: "Feld_1095C_2025.pdf" },
] as const;

const FIRM_WORDS =
  /Accrued|\bAgent\b|Uploaded – needs review|Received ✓|review point|Action required|confidence/;

const WIDTHS = [
  { width: 1400, height: 900 },
  { width: 390, height: 844 },
] as const;

for (const size of WIDTHS) {
  test.describe(`POR-04 at ${String(size.width)}`, () => {
    test.use({ viewport: size, deviceScaleFactor: 2, reducedMotion: "reduce" });

    for (const { st, ready } of ARTBOARDS) {
      test(`POR-04${st}: renders, white-labelled, one primary, and axe finds nothing serious`, async ({
        page,
      }) => {
        await page.goto(`/components/screens/POR-04?st=${st}&frame=1`);
        const board = page.locator(`[data-artboard='${st}']`);
        await expect(board).toBeVisible();
        await expect(board.getByText(ready).first()).toBeVisible();
        expect(await board.innerText()).not.toMatch(FIRM_WORDS);
        const attrs = await board.evaluate((el) =>
          [...el.querySelectorAll("*")]
            .flatMap((n) =>
              ["aria-label", "title", "alt", "placeholder"].map((a) => n.getAttribute(a)),
            )
            .filter((v): v is string => v !== null)
            .join(" "),
        );
        expect(attrs).not.toMatch(FIRM_WORDS);
        expect(await board.locator("[data-variant='primary']").count()).toBeLessThanOrEqual(1);
        const { violations } = await new AxeBuilder({ page })
          .include(`[data-artboard='${st}']`)
          .analyze();
        const serious = violations
          .filter((v) => SERIOUS.has(v.impact ?? ""))
          .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
        expect(serious).toEqual([]);
      });
    }
  });
}
