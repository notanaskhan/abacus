// F-05-T42 (independent, ADR-078): E2's placement in a real browser, over the C-07 wired specimen.
// F-05 G1: "The anchored popover sits 8 px beside the lit cell and flips when space runs out."
// C-07: "Anchored 8px to the right of the lit cell, top-aligned. It flips left when there's no
// room." The gallery calls no API: only the dev server is needed (`make dev-fixtures`).
import { expect, test, type Page } from "@playwright/test";

async function pinFirstCitation(page: Page, row: "wired" | "edge" = "wired") {
  await page.goto("/components#c-07-wired");
  const board = page.locator(`section[id="c-07-wired"] [data-specimen="${row}"]`);
  const marker = board.getByRole("button", { name: /^Citation \d:/ }).first();
  await board.evaluate((el) => {
    el.scrollIntoView({ block: "center" });
  });
  await marker.click();
  const popover = page.locator('[data-popover="anchored"]');
  await expect(popover).toBeVisible();
  const cell = board.locator('[data-match-kind="cell"][data-lit]');
  await expect(cell).toHaveCount(1);
  return { popover, cell, marker };
}

test("the popover sits 8px right of the lit cell, top-aligned", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { popover, cell } = await pinFirstCitation(page);
  const p = await popover.boundingBox();
  const c = await cell.boundingBox();
  expect(p).not.toBeNull();
  expect(c).not.toBeNull();
  if (p === null || c === null) return;
  expect(Math.abs(p.x - (c.x + c.width) - 8)).toBeLessThanOrEqual(1);
  expect(Math.abs(p.y - c.y)).toBeLessThan(1);
  expect(Math.round(p.width)).toBe(372);
});

test("with no room on the right it flips to the left of the lit cell", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { popover, cell } = await pinFirstCitation(page, "edge");
  const p = await popover.boundingBox();
  const c = await cell.boundingBox();
  if (p === null || c === null) throw new Error("no boxes");
  expect(await popover.getAttribute("data-side")).toBe("left");
  expect(Math.abs(c.x - (p.x + p.width) - 8)).toBeLessThanOrEqual(1);
});

test("Escape closes it, darkens the cell and returns focus to the marker", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { popover, cell, marker } = await pinFirstCitation(page);
  await page.keyboard.press("Escape");
  await expect(popover).toHaveCount(0);
  await expect(cell).toHaveCount(0);
  await expect(marker).toBeFocused();
});
