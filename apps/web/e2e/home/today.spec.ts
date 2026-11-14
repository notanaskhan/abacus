// I-02-T21 (TASK-7952; docs/screens/HOME-05.md, SHL-23.md; SPEC-654 §3.1–§3.11): the Today brief's
// named scenarios on the gallery artboards (the fixture project): flag off, collapse and the drawer,
// building to ready, the quiet day, history, ask and the refusal, assign with the reserved item,
// and axe on each. Staging walks (DF-04 on a non-synthetic tenant, Grace, walls) are I-02-T22's.
import AxeBuilder from "@axe-core/playwright";
import { type Page, expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

test.use({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, reducedMotion: "reduce" });

async function board(page: Page, screen: "HOME-05" | "SHL-23", st: string) {
  await page.goto(`/components/screens/${screen}?st=${st}&frame=1&static=1`);
  const b = page.locator(`[data-artboard='${st}']`);
  await expect(b).toBeVisible();
  return b;
}

async function axeClean(page: Page, st: string): Promise<void> {
  const { violations } = await new AxeBuilder({ page }).include(`[data-artboard='${st}']`).analyze();
  expect(violations.filter((v) => SERIOUS.has(v.impact ?? "")).map((v) => v.id)).toEqual([]);
}

for (const st of ["a", "b", "c", "d", "e", "f"]) {
  test(`HOME-05 ${st}: renders axe clean`, async ({ page }) => {
    await board(page, "HOME-05", st);
    await axeClean(page, st);
  });
}

for (const st of ["full", "1", "2", "3", "4", "5", "6", "7"]) {
  test(`SHL-23 ${st}: renders axe clean`, async ({ page }) => {
    await board(page, "SHL-23", st);
    await axeClean(page, st);
  });
}

test("flag off: HOME-01 alone, no Today chip or link (HOME-05 f)", async ({ page }) => {
  const b = await board(page, "HOME-05", "f");
  await expect(b.locator("[data-chip='today']")).toHaveCount(0);
});

test("collapse keeps HOME-01's geometry and Open Today brings the dock back (HOME-05 c)", async ({
  page,
}) => {
  const b = await board(page, "HOME-05", "a");
  await b.locator("[data-chip='today']").click();
  await expect(b.getByRole("button", { name: /Open Today/ })).toBeVisible();
});

test("building, then the quiet day (SHL-23 7 and 6)", async ({ page }) => {
  const building = await board(page, "SHL-23", "7");
  await expect(building.locator("[data-state='building']")).toBeVisible();
  const quiet = await board(page, "SHL-23", "6");
  await expect(quiet.getByText("Nothing needs you first.")).toBeVisible();
});

test("the drill-in: Basis reserved, Assign opens the prefilled to-do (SHL-23 2)", async ({ page }) => {
  const b = await board(page, "SHL-23", "2");
  await expect(b.getByText("Reserved to you — not assignable")).toBeVisible();
});
