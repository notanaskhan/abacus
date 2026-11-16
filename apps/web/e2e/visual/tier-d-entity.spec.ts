// Tier D for T-05's entity-return screens (T-05-T69; T-05 §5.4 "Tier D (blocking)"): exact
// computed sizes, not pixels, so it needs no baseline and blocks wherever the visual project runs.
// From the T-05 epic and the TXP handoff specs: subbar 42, tabsbar 50, control bar 44, tally strip
// 52, pane header 46 with a 14.5/500 title, pane radius 12, body 13/15.6 Geist, grid column-letter
// row 20 and row numbers 34. Not asserted: the body's 15.6 line (an open decision, below).
import { type Locator, type Page, expect, test } from "@playwright/test";
import { openGallery } from "./support";

async function box(target: Locator): Promise<{ width: number; height: number }> {
  const b = await target.first().boundingBox();
  if (b === null) throw new Error("no box");
  return { width: Math.round(b.width), height: Math.round(b.height) };
}

async function board(page: Page, screen: string, st: string): Promise<Locator> {
  await openGallery(page, `screens/${screen}?st=${st}`);
  const frame = page.locator(`[data-artboard='${st}']`).first();
  await expect(frame.getByText("Ridgeline Property Partners, LP").first()).toBeVisible();
  return frame;
}

const SCREENS = ["TXP-00", "TXP-01", "TXP-02", "TXP-05", "TXP-07", "TXP-10", "TXP-11"] as const;

for (const screen of SCREENS) {
  test(`${screen}a: subbar 42, tabsbar 50, body Geist 13`, async ({ page }) => {
    const frame = await board(page, screen, "a");
    expect((await box(frame.locator("[data-shell='record-header']"))).height).toBe(42);
    expect((await box(frame.locator("[data-entity='tabsbar']"))).height).toBe(50);
    const body = await frame
      .locator("[data-layout='entity-return']")
      .evaluate((el) => [getComputedStyle(el).fontSize, getComputedStyle(el).fontFamily]);
    expect(body[0]).toBe("13px");
    expect(body[1]).toMatch(/^Geist\b/);
  });
}

// The 15.6 line is the open decision tier-d.spec.ts holds ("body line height": the body keeps 1.45
// until F-05-T05's question closes); it is fixme there and here, never asserted to fail.
test.fixme("entity screens: the body line is 15.6", () => {});

for (const screen of ["TXP-02", "TXP-05", "TXP-07"] as const) {
  test(`${screen}a: control bar 44, tally strip 52`, async ({ page }) => {
    const frame = await board(page, screen, "a");
    expect((await box(frame.locator("[data-entity='control-bar']"))).height).toBe(44);
    const strip = frame.locator("[data-tally-strip]").first();
    for (const cell of await strip.locator(":scope > *").all()) {
      expect((await box(cell)).height).toBe(52);
    }
  });
}

// TXP-01's and TXP-10's headers are their templates' (T10 DocumentOnWell, T9 QueueDetailLayout),
// measured by those templates' Tier D; TXP-00's rail and workbook panes are its own.
for (const screen of ["TXP-00"] as const) {
  test(`${screen}a: pane header 46 with a 14.5/500 title, pane radius 12`, async ({ page }) => {
    const frame = await board(page, screen, "a");
    const title = frame.locator(`[data-screen='${screen}'] h2`).first();
    expect((await box(title)).height).toBe(46);
    const font = await title.evaluate((el) => [
      getComputedStyle(el).fontSize,
      getComputedStyle(el).fontWeight,
    ]);
    expect(font).toEqual(["14.5px", "500"]);
    const radius = await title.evaluate(
      (el) => getComputedStyle(el.parentElement ?? el).borderTopLeftRadius,
    );
    expect(radius).toBe("12px");
  });
}

test("TXP-11a: column-letter row 20, row numbers 34", async ({ page }) => {
  const frame = await board(page, "TXP-11", "a");
  const grid = frame.getByRole("grid").first();
  expect((await box(grid.getByRole("columnheader", { name: "A", exact: true }))).height).toBe(20);
  expect((await box(grid.getByRole("rowheader", { name: "1", exact: true }))).width).toBe(34);
});
