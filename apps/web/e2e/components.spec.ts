// SPEC-048 AC-3, AC-4, AC-10 (F-05-T09): axe on /components/** under the AA ladder, and the
// gallery's contrast parameter. The gallery calls no API, so only the dev server is needed
// (`make dev-fixtures` or `make dev`).
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

async function expectNoSeriousViolations(page: Page): Promise<void> {
  const { violations } = await new AxeBuilder({ page }).analyze();
  const serious = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(
    serious.map((v) => `${v.id} (${v.impact ?? "?"}): ${v.help}`),
    "serious or critical accessibility violations",
  ).toEqual([]);
}

test("ac3: axe finds nothing serious on /components/**", async ({ page }) => {
  await page.goto("/components");
  await expect(page.getByRole("heading", { name: "Components", level: 1 })).toBeVisible();
  await expectNoSeriousViolations(page);

  await page.goto("/components/tokens");
  await expect(page.getByRole("table", { name: /Every colour token/ })).toBeVisible();
  await expectNoSeriousViolations(page);

  await page.goto("/components/icons");
  await expect(page.getByRole("table", { name: /Every registered icon name/ })).toBeVisible();
  await expectNoSeriousViolations(page);

  await page.goto("/components/screens/NO-SUCH-SCREEN");
  await expect(page.getByText("Not built")).toBeVisible();
  await expectNoSeriousViolations(page);
});

test("ac4: ?contrast=reference sets data-contrast on <html>", async ({ page }) => {
  await page.goto("/components/tokens");
  await expect(page.getByRole("table", { name: /Every colour token/ })).toBeVisible();
  await expect(page.locator("html")).not.toHaveAttribute("data-contrast", /.*/);
  await page.goto("/components/tokens?contrast=reference");
  await expect(page.locator("html")).toHaveAttribute("data-contrast", "reference");
});

test("ac15: /_ds no longer routes", async ({ page }) => {
  await page.goto("/_ds");
  await expect(page.getByText("Page not found")).toBeVisible();
});
