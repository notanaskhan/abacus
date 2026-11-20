// A-08-T37 (TASK-8756): the helper is not vacuous. A page with a seeded serious violation (an image
// button with no name) makes seriousIn report it, so a clean result means a clean page.
import { expect, test } from "@playwright/test";
import { seriousIn } from "./gallery-boards";

test("a seeded serious violation is reported", async ({ page }) => {
  await page.setContent(
    `<div data-artboard="x"><button><svg width="10" height="10"></svg></button></div>`,
  );
  const found = await seriousIn(page, "x");
  expect(found.some((v) => v.startsWith("button-name"))).toBe(true);
});
