// POR-03 a, c, e, f, g and h in fixture mode (R-01-T06; build-screen-from-handoff §5,
// portal-screen): every part-1 scenario at 1440×900, DPR 2, from the /components gallery on
// fixtures, with axe at zero serious or critical findings, no "Accrued" in the text or in any
// attribute a person or assistive technology meets, and no firm status word, agent name or bell.
// b, motion, c2, d, i and the 390 layout are R-01-T10's; parity is R-01-T31's.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/POR-03.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS = [
  { st: "a", ready: "Form 1095-C From Mercer Hill Health" },
  { st: "c", ready: "Suggested — Brightwater Hale will confirm" },
  { st: "e", ready: "Marked done Sep 14 · Brightwater Hale will review your documents" },
  { st: "f", ready: "Not applicable this year" },
  { st: "g", ready: "Returned · wrong year" },
  { st: "h", ready: "You’re all caught up." },
] as const;

const FIRM_WORDS =
  /Accrued|\bAgent\b|Uploaded – needs review|Received ✓|In review|confidence|Matched \d+%/;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of ARTBOARDS) {
  test(`POR-03${st}: renders, white-labelled, and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/POR-03?st=${st}&frame=1`);
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
    await expect(board.getByRole("button", { name: /notification/i })).toHaveCount(0);
    const { violations } = await new AxeBuilder({ page })
      .include(`[data-artboard='${st}']`)
      .analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}
