// Tier D for the portal's 390 layouts that have no handoff PNG (R-01-T31; the POR-03, POR-04 and
// POR-14 contracts' "390" and "M" rows): computed geometry, not pixels, so it needs no baseline and
// blocks where the visual project runs. The gallery draws POR-04 and POR-14 at 390 with `&w=390`.
//
// Measured against the contracts:
// - POR-03 M: header 56, tab bar 64 at the phone's foot.
// - POR-04 390: the sheet full width with a 56 header, over the 56 mobile header.
// - POR-14 390: header 56, no tab bar.
// Two contract lines do not hold yet and are kept as expected failures, so the day they hold the run
// says so (R-01-T31 findings, docs/screens POR-03/04/14 "Open gaps"): every target at least 44 × 44
// (Close, Upload…, Send comment, Take a photo and the room's "Drop files here" are 19–36 tall),
// and POR-04's sheet from y44 (it starts at y16).
import { type Locator, type Page, expect, test } from "@playwright/test";

test.use({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, reducedMotion: "reduce" });

interface Box {
  y: number;
  height: number;
  width: number;
}

async function open(page: Page, id: string, st: string): Promise<Locator> {
  const wide = id === "POR-03" ? "" : "&w=390";
  await page.goto(`/components/screens/${id}?st=${st}&frame=1&static=1${wide}`);
  const phone = page.locator(`[data-artboard='${st}'] [data-frame='phone']`).first();
  await expect(phone).toBeVisible();
  return phone;
}

/** A box relative to the phone's top edge. */
async function within(phone: Locator, target: Locator): Promise<Box> {
  const p = await phone.boundingBox();
  const b = await target.boundingBox();
  if (p === null || b === null) throw new Error("no box");
  return { y: Math.round(b.y - p.y), height: Math.round(b.height), width: Math.round(b.width) };
}

/** The interactive targets under 44 × 44 in `scope`. */
async function smallTargets(scope: Locator): Promise<string[]> {
  return scope.evaluate((root) =>
    [...root.querySelectorAll("button, a[href], [role='tab'], [role='button'], input")]
      .filter((el) => (el as HTMLElement).offsetParent !== null)
      .map((el) => ({ el, b: el.getBoundingClientRect() }))
      .filter(({ b }) => b.width > 0 && (b.width < 44 || b.height < 44))
      .map(
        ({ el, b }) =>
          `${(el.getAttribute("aria-label") ?? (el as HTMLElement).innerText).trim().slice(0, 40)} ${String(Math.round(b.width))}×${String(Math.round(b.height))}`,
      ),
  );
}

test("POR-03 M: header 56 and the 64 tab bar at the foot", async ({ page }) => {
  const phone = await open(page, "POR-03", "M");
  const header = await within(phone, phone.locator("[data-shell='mobile-header']"));
  const tabs = await within(phone, phone.locator("[data-shell='mobile-tab-bar']"));
  expect([header.y, header.height, header.width]).toEqual([0, 56, 390]);
  expect([tabs.height, tabs.y + tabs.height]).toEqual([64, 844]);
});

for (const st of ["a", "b", "c", "d", "g"] as const) {
  test(`POR-04${st} at 390: the sheet full width with a 56 header`, async ({ page }) => {
    const phone = await open(page, "POR-04", st);
    const sheet = page.getByRole("dialog").first();
    await expect(sheet).toBeVisible();
    const box = await within(phone, sheet);
    expect(box.width).toBe(390);
    const header = await within(phone, sheet.locator(":scope > *").first());
    expect(header.height).toBe(56);
  });
}

for (const st of ["a", "b", "c", "d", "e", "f"] as const) {
  test(`POR-14${st} at 390: header 56, no tab bar`, async ({ page }) => {
    const phone = await open(page, "POR-14", st);
    const header = await within(phone, phone.locator("[data-shell='mobile-header']"));
    expect([header.y, header.height]).toEqual([0, 56]);
    await expect(phone.locator("[data-shell='mobile-tab-bar']")).toHaveCount(0);
  });
}

test.describe("contract lines that do not hold yet (R-01-T31 findings)", () => {
  test("POR-04a at 390: every target at least 44 × 44", async ({ page }) => {
    test.fail(true, "Close 30×30, Upload… 49×19, Send comment 32×32, Take a photo 342×36");
    await open(page, "POR-04", "a");
    expect(await smallTargets(page.getByRole("dialog").first())).toEqual([]);
  });

  test("POR-14a at 390: every target at least 44 × 44", async ({ page }) => {
    test.fail(true, "Drop files here 126×30, Send comment 28×28");
    const phone = await open(page, "POR-14", "a");
    expect(await smallTargets(phone)).toEqual([]);
  });

  test("POR-04a at 390: the sheet starts at y44", async ({ page }) => {
    test.fail(true, "the full-screen sheet starts at y16");
    const phone = await open(page, "POR-04", "a");
    expect((await within(phone, page.getByRole("dialog").first())).y).toBe(44);
  });
});
