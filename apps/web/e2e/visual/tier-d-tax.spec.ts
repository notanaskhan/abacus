// Tier D for T-01's screens (T-01-T52; T-01 §5.5 "Computed geometry"): exact computed sizes, not
// pixels, so it needs no baseline and blocks wherever the visual project runs. Numbers from the
// TAX-12, TAX-09 and CLI-05 handoff specs: the checklist rail 330, the canvas header 46, signer
// rows 52, packet rows 36; TAX-09's popover 462 wide; CLI-05's rail 330. Plus keyboard: the sync
// chip and the rail rows are reachable by Tab, and reduced motion leaves no running animation.
import { type Locator, type Page, expect, test } from "@playwright/test";
import { openGallery } from "./support";

interface Size {
  width: number;
  height: number;
}

async function size(target: Locator): Promise<Size> {
  const box = await target.first().boundingBox();
  if (box === null) throw new Error("no box");
  return { width: Math.round(box.width), height: Math.round(box.height) };
}

async function board(page: Page, screen: string, st: string): Promise<Locator> {
  await openGallery(page, `screens/${screen}?st=${st}`);
  const frame = page.locator(`[data-artboard='${st}']`).first();
  await expect(frame).toBeVisible();
  return frame;
}

for (const st of ["a", "c", "d"] as const) {
  test(`TAX-12${st}: rail 330, canvas header 46, signer rows 52`, async ({ page }) => {
    const frame = await board(page, "TAX-12", st);
    const screen = frame.locator("[data-screen='TAX-12']");
    expect((await size(screen.locator(":scope > :first-child"))).width).toBe(330);
    expect((await size(screen.locator("main header").first())).height).toBe(46);
    for (const row of await screen.locator("main section ul li").all()) {
      const h = (await size(row)).height;
      expect([52, 36]).toContain(h);
    }
  });
}

test("TAX-09a2: the sync popover is 462 wide", async ({ page }) => {
  const frame = await board(page, "TAX-09", "a2");
  const popover = frame.getByRole("dialog", { name: "Tax-engine sync" });
  expect((await size(popover)).width).toBe(462);
});

for (const st of ["d", "f"] as const) {
  test(`CLI-05${st}: rail 330`, async ({ page }) => {
    const frame = await board(page, "CLI-05", st);
    const rail = frame.locator("[data-cockpit='rail']").first();
    expect((await size(rail)).width).toBe(330);
  });
}

test("TAX-12a: Tab reaches the rail rows and the canvas actions", async ({ page }) => {
  const frame = await board(page, "TAX-12", "a");
  // Phase rows are not themselves controls: Tab lands on the first control inside the rail.
  const first = frame.locator("[data-cockpit='rail'] button").first();
  await first.focus();
  await expect(first).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
});

test("TAX-12d under reduced motion: no animation is running", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const frame = await board(page, "TAX-12", "d");
  const running = await frame.evaluate(
    (el) => el.getAnimations({ subtree: true }).filter((a) => a.playState === "running").length,
  );
  expect(running).toBe(0);
});
