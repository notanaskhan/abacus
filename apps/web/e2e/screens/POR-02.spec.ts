// POR-02 a, b, c, f in fixture mode (P-08-T15; build-screen-from-handoff §5, portal-screen): every
// scenario at 1440×900, DPR 2, from the /components gallery on fixtures, with axe at zero serious
// or critical findings, and no "Accrued" anywhere on the white-labelled page. The 720 and 390
// widths (M) are P-08-T23's; parity is P-08-T27's.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/POR-02.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS = [
  { st: "a", ready: "Upload 2 documents" },
  { st: "b", ready: "Welcome to Brightwater Hale's client portal." },
  { st: "c", ready: "You're all set for now." },
  { st: "f", ready: null },
] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of ARTBOARDS) {
  test(`POR-02${st}: renders, white-labelled, and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/POR-02?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    if (ready === null) {
      await expect(board.getByRole("status", { name: "Loading" })).toBeVisible();
    } else {
      await expect(board.getByText(ready).first()).toBeVisible();
    }
    expect(await board.innerText()).not.toMatch(/Accrued/);
    const { violations } = await new AxeBuilder({ page })
      .include(`[data-artboard='${st}']`)
      .analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}
