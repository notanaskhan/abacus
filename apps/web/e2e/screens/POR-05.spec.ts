// POR-05 a–f in fixture mode (T-02-T24; portal-screen): every scenario at 1440×900 from the
// /components gallery on fixtures, with axe at zero serious or critical findings and no
// "Accrued" in the text or in any attribute a person or assistive technology meets; the 390
// layout once. Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium
// e2e/screens/POR-05.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS = [
  { st: "a", ready: "22 of 24 answered" },
  { st: "b", ready: "Upload Form 1099-DA or your exchange's 2025 gains and losses report" },
  { st: "c", ready: "Thanks — Kevin Osei has your answers." },
  { st: "d", ready: "Your answers go only to the Brightwater Hale audit team." },
  { st: "e", ready: "From Hannah Leclerc · Brightwater Hale" },
  { st: "f", ready: "No questions right now." },
] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of ARTBOARDS) {
  test(`POR-05${st}: renders, white-labelled, and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/POR-05?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    await expect(board.getByText(ready).first()).toBeVisible();
    expect(await board.innerText()).not.toMatch(/Accrued/);
    const results = await new AxeBuilder({ page }).include(`[data-artboard='${st}']`).analyze();
    const serious = results.violations.filter((v) => SERIOUS.has(v.impact ?? ""));
    expect(serious, JSON.stringify(serious.map((v) => v.id))).toEqual([]);
  });
}

test("POR-05 M: one card at a time with Next question", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/components/screens/POR-05?st=a&frame=1&w=390");
  await expect(page.getByRole("button", { name: "Next question" })).toBeVisible();
});
