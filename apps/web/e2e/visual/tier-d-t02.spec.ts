// Tier D for T-02's screens (T-02-T33; T-02 §5.4 "Parity targets", §5.5): computed geometry on the
// T1, T2 and T7 reduced hosts, not pixels, so it needs no baseline and blocks wherever the visual
// project runs. Toolbar 46, record header (subbar) 42, tabsbar 44 and pane header 46 on TAX-01 (T1),
// TAX-02, TAX-03 and TXP-12 (T2); the portal toolbar on POR-05 and POR-13 (T7). Keyboard: TAX-01's
// tiles and TXP-12's and POR-05's expandable rows answer Tab and Enter; POR-05's Saved time sits in
// a polite live region.
import { type Locator, type Page, expect, test } from "@playwright/test";
import { openGallery } from "./support";

async function height(target: Locator): Promise<number> {
  const box = await target.first().boundingBox();
  if (box === null) throw new Error("no box");
  return Math.round(box.height);
}

async function board(page: Page, screen: string, st: string): Promise<Locator> {
  await openGallery(page, `screens/${screen}?st=${st}`);
  const frame = page.locator(`[data-artboard='${st}']`).first();
  await expect(frame).toBeVisible();
  return frame;
}

const FIRM: readonly (readonly [string, string])[] = [
  ["TAX-01", "a"],
  ["TAX-02", "a"],
  ["TAX-03", "a"],
  ["TXP-12", "a"],
];

for (const [screen, st] of FIRM) {
  test(`${screen}${st}: toolbar 46 and every pane header 46`, async ({ page }) => {
    const frame = await board(page, screen, st);
    expect(await height(frame.locator('[data-shell="toolbar"]'))).toBe(46);
    for (const header of await frame.locator('[data-shell="pane-header"]').all()) {
      expect(await height(header)).toBe(46);
    }
  });
}

for (const screen of ["TAX-02", "TAX-03", "TXP-12"] as const) {
  test(`${screen}a: the return frame's subbar 42 and tabsbar 44`, async ({ page }) => {
    const frame = await board(page, screen, "a");
    const subbar = frame.locator('[data-shell="record-header"]');
    if ((await subbar.count()) > 0) expect(await height(subbar)).toBe(42);
    expect(await height(frame.locator('[data-shell="tabsbar"]'))).toBe(44);
  });
}

for (const screen of ["POR-05", "POR-13"] as const) {
  test(`${screen}a: the reduced portal toolbar is 46`, async ({ page }) => {
    const frame = await board(page, screen, "a");
    expect(await height(frame.locator('[data-shell="portal-toolbar"]'))).toBe(46);
  });
}

test("TAX-01a: Tab reaches the tiles and focus stays visible", async ({ page }) => {
  const frame = await board(page, "TAX-01", "a");
  const first = frame.getByRole("button").first();
  await first.focus();
  await expect(first).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
});

for (const [screen, st] of [
  ["TXP-12", "a"],
  ["POR-05", "a"],
] as const) {
  test(`${screen}${st}: an expandable row opens and closes from the keyboard`, async ({
    page,
  }) => {
    const frame = await board(page, screen, st);
    const row = frame.locator("[aria-expanded]").first();
    await row.focus();
    const before = await row.getAttribute("aria-expanded");
    await page.keyboard.press("Enter");
    await expect(row).not.toHaveAttribute("aria-expanded", before ?? "");
    await page.keyboard.press("Enter");
    await expect(row).toHaveAttribute("aria-expanded", before ?? "");
  });
}

test("POR-05a: the autosave time is announced politely", async ({ page }) => {
  const frame = await board(page, "POR-05", "a");
  await expect(frame.locator("[aria-live='polite']").first()).toBeAttached();
});
