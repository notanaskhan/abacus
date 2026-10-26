// POR-14 a–f in fixture mode (R-01-T14, R-01-T21; portal-screen): the third-party room at 1400 and
// on the 390 preset, from the /components gallery on fixtures, with axe at zero serious or critical
// findings and no "Accrued", no firm status word and nothing of the client's own documents (INV-4:
// a third party sees only its delegated requests). Parity is R-01-T31's.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/POR-14.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS = [
  { st: "a", ready: "4 of 9 uploaded" },
  { st: "b", ready: "You uploaded Sep 22 · Brightwater Hale is reviewing it" },
  { st: "c", ready: "Returned · wrong period" },
  { st: "d", ready: "1 of 2 uploaded" },
  { st: "e", ready: "9 of 9 uploaded" },
  { st: "f", ready: "This link has expired or was already used" },
] as const;

const FIRM_WORDS = /Accrued|\bAgent\b|Uploaded – needs review|Received ✓|confidence/;
// The client's own requests (Dana Kowalski's census and plan documents) never reach the room.
const CLIENT_ONLY = /Employee census file|Form 1095-C/;

const WIDTHS = [
  { width: 1400, height: 900 },
  { width: 390, height: 844 },
] as const;

for (const size of WIDTHS) {
  test.describe(`POR-14 at ${String(size.width)}`, () => {
    test.use({ viewport: size, deviceScaleFactor: 2, reducedMotion: "reduce" });

    for (const { st, ready } of ARTBOARDS) {
      test(`POR-14${st}: renders, white-labelled, scoped, and axe finds nothing serious`, async ({
        page,
      }) => {
        await page.goto(`/components/screens/POR-14?st=${st}&frame=1`);
        const board = page.locator(`[data-artboard='${st}']`);
        await expect(board).toBeVisible();
        await expect(board.getByText(ready).first()).toBeVisible();
        const text = await board.innerText();
        expect(text).not.toMatch(FIRM_WORDS);
        expect(text).not.toMatch(CLIENT_ONLY);
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
