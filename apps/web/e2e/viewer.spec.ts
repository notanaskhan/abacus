// F-05-T48 (ADR-078), the browser half: "every viewer state is axe clean." The E5 SourceViewer
// specimen holds the full and evidence variants and the processing, password-protected,
// can't-preview and loading states; this walks them idle, lit (a region pinned, its linked figure
// shown), with Find open, and after a logged reveal. Plus F-05 G3 in a real browser: only image
// pages, and no Download in either bar. The gallery calls no API (`make dev-fixtures`).
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const SECTION = "#c-08-source-viewer";

async function serious(page: Page): Promise<string[]> {
  const { violations } = await new AxeBuilder({ page }).include(SECTION).analyze();
  return violations
    .filter((v) => SERIOUS.has(v.impact ?? ""))
    .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
}

test.beforeEach(async ({ page }) => {
  await page.goto("/components");
  await expect(page.locator(SECTION)).toBeVisible();
  await page.locator(SECTION).scrollIntoViewIfNeeded();
});

test("every viewer state is axe clean: idle, lit, finding and revealed", async ({ page }) => {
  const section = page.locator(SECTION);
  expect(await serious(page), "idle and the four states").toEqual([]);

  await section.getByRole("button", { name: "Ordinary dividends 1a" }).click();
  await expect(section.locator("[data-linked-figure]")).toBeVisible();
  expect(await serious(page), "a region pinned with its tag").toEqual([]);

  await section.getByRole("button", { name: "Find in document" }).first().click();
  await expect(section.getByRole("textbox", { name: "Find in document" })).toBeFocused();
  expect(await serious(page), "Find open").toEqual([]);
  await page.keyboard.press("Escape");

  await section.getByRole("button", { name: "Reveal (logged)" }).click();
  await expect(section.locator("[data-reveal-note]")).toHaveText(
    "Revealed by Samuel Ito · 9:31 AM · logged to the audit trail",
  );
  expect(await serious(page), "after the reveal").toEqual([]);
});

test("pages are images only and Download is in no bar", async ({ page }) => {
  const section = page.locator(SECTION);
  await expect(section.locator("iframe, object, embed, canvas")).toHaveCount(0);
  const srcs = await section
    .locator("[data-page] img")
    .evaluateAll((imgs) => imgs.map((i) => i.getAttribute("src") ?? ""));
  expect(srcs.length).toBeGreaterThan(0);
  for (const src of srcs) expect(src).toMatch(/^data:image\/png;base64,/);
  for (const bar of await section.locator("[data-viewer-bar]").all())
    await expect(bar).not.toContainText(/download/i);
});

test("regions stay invisible until lit", async ({ page }) => {
  const region = page.locator(`${SECTION} [data-match-kind="region"]`).first();
  const idle = await region.evaluate((el) => getComputedStyle(el).backgroundColor);
  expect(idle).toBe("rgba(0, 0, 0, 0)");
});
