// F-05-T22: independent acceptance tests for E3 (ADR-078), written from F-05 §3.E (E1, E2) and
// plan 04 E3, not from the overlay code. They drive the /components gallery's stacking, drawer and
// sheet specimens in a real browser, where focus is real. The gallery calls no API: only the dev
// server is needed (`make dev-fixtures`).
//
// E1: Escape closes popover, then dialog, then drawer, and focus returns to each trigger; O3/O4/O6
// and a modal O2 trap focus; a peek O2 is complementary with no trap; a dirty O3 asks "Discard
// changes?" instead of closing. (The ?ov= round trip and INV-1 are in the Vitest suites
// apps/web/src/app-core/e3-acceptance.test.ts and packages/ui/src/components/e3-acceptance.test.ts.)
import { expect, test, type Page } from "@playwright/test";

async function gallery(page: Page): Promise<void> {
  await page.goto("/components");
  await expect(page.getByRole("heading", { name: "Components", level: 1 })).toBeVisible();
}

// The live peek, not the held specimen copy drawn inside the C-23 section.
const livePeek = (page: Page) =>
  page
    .getByRole("complementary", { name: "2025 Form 1065 · Ridgeline" })
    .and(page.locator(":not(#c-23-drawer *)"));

const activeName = (page: Page): Promise<string> =>
  page.evaluate(() => (document.activeElement?.textContent ?? "").trim());

test("E1: Escape closes popover, dialog, drawer in that order; focus returns to each trigger", async ({
  page,
}) => {
  await gallery(page);
  const stacking = page.locator("#o1-o6-stacking");
  const openDrawer = stacking.getByRole("button", { name: "Open the request drawer" });
  await openDrawer.scrollIntoViewIfNeeded();
  await openDrawer.click();
  const drawer = page.getByRole("dialog", { name: "Request" });
  await expect(drawer).toBeVisible();
  await drawer.getByRole("button", { name: "Assign…" }).click();
  const dialog = page.getByRole("dialog", { name: "Assign to" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Reviewers…" }).click();
  const popover = page.getByRole("dialog", { name: "Reviewers" });
  await expect(popover).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(popover).toBeHidden();
  await expect(dialog).toBeVisible();
  // The layer under a modal is hidden from assistive technology, but still there.
  await expect(page.getByRole("dialog", { name: "Request", includeHidden: true })).toBeAttached();
  expect(await activeName(page)).toBe("Reviewers…");

  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(drawer).toBeVisible();
  expect(await activeName(page)).toBe("Assign…");

  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
  expect(await activeName(page)).toBe("Open the request drawer");
});

test("E1: a modal dialog traps focus", async ({ page }) => {
  await gallery(page);
  const stacking = page.locator("#o1-o6-stacking");
  await stacking.getByRole("button", { name: "Open the request drawer" }).click();
  await page
    .getByRole("dialog", { name: "Request" })
    .getByRole("button", { name: "Assign…" })
    .click();
  const dialog = page.getByRole("dialog", { name: "Assign to" });
  await expect(dialog).toBeVisible();
  for (let i = 0; i < 12; i += 1) {
    await page.keyboard.press(i % 3 === 2 ? "Shift+Tab" : "Tab");
    const inside = await dialog.evaluate((el) => el.contains(document.activeElement));
    expect(inside, `focus left the dialog after ${String(i + 1)} presses`).toBe(true);
  }
});

test("E1: a modal drawer traps focus", async ({ page }) => {
  await gallery(page);
  await page.locator("#c-23-drawer").getByRole("button", { name: "Notifications" }).click();
  const drawer = page.getByRole("dialog", { name: "Notifications" });
  await expect(drawer).toBeVisible();
  for (let i = 0; i < 10; i += 1) {
    await page.keyboard.press("Tab");
    expect(await drawer.evaluate((el) => el.contains(document.activeElement))).toBe(true);
  }
});

test("E1: a peek drawer is complementary, with no trap and no focus move", async ({ page }) => {
  await gallery(page);
  const section = page.locator("#c-23-drawer");
  const trigger = section.getByRole("button", { name: "Peek a record" });
  await trigger.click();
  const peek = livePeek(page);
  await expect(peek).toBeVisible();
  expect(await peek.getAttribute("aria-modal")).toBeNull();
  // No live modal layer (held specimen copies sit inside the gallery sections).
  await expect(page.getByRole("dialog").and(page.locator(":not(section[id] *)"))).toHaveCount(0);
  // Focus stays on the page: the trigger keeps it, and Tab can reach the page beyond the peek.
  await expect(trigger).toBeFocused();
  await page.keyboard.press("Tab");
  const inPeek = await peek.evaluate((el) => el.contains(document.activeElement));
  const next = await activeName(page);
  expect(inPeek && next === "").toBe(false);
});

test("E1: never two drawers — opening the peek replaces the open drawer", async ({ page }) => {
  await gallery(page);
  const section = page.locator("#c-23-drawer");
  await section.getByRole("button", { name: "Notifications" }).click();
  await expect(page.getByRole("dialog", { name: "Notifications" })).toBeVisible();
  // The modal drawer hides the page from assistive technology; press the peek trigger directly.
  await section
    .getByRole("button", { name: "Peek a record", includeHidden: true })
    .dispatchEvent("click");
  await expect(livePeek(page)).toBeVisible();
  await expect(
    page.getByRole("dialog", { name: "Notifications", includeHidden: true }),
  ).toHaveCount(0);
});

test("E1: a dirty sheet asks “Discard changes?” instead of closing", async ({ page }) => {
  await gallery(page);
  const section = page.locator("#o3-sheet-modal");
  await section.getByRole("button", { name: "Raise issue…" }).first().click();
  const sheet = page.getByRole("dialog", { name: "Raise Issue" });
  await expect(sheet).toBeVisible();
  await sheet.getByRole("textbox").first().fill("Unreconciled suspense balance");

  // The scrim: a click outside the sheet.
  await page.mouse.click(8, 8);
  const guard = page.getByRole("alertdialog", { name: "Discard changes?" });
  await expect(guard).toBeVisible();
  await expect(
    page.getByRole("dialog", { name: "Raise Issue", includeHidden: true }),
  ).toBeAttached();
  await guard.getByRole("button", { name: /keep|cancel/i }).click();
  await expect(guard).toBeHidden();
  await expect(sheet).toBeVisible();

  // Escape asks too; Discard closes the sheet.
  await page.keyboard.press("Escape");
  await expect(guard).toBeVisible();
  await guard.getByRole("button", { name: "Discard" }).click();
  await expect(sheet).toBeHidden();
});
