// Keyboard suites for the entity screens (T-05-T69; T-05 §5.5, §10 item 4): the TXP-11 grid is an
// ARIA grid with arrow-key navigation, Enter and F2 to edit and Esc to cancel, and the selected
// address is announced; O4 (TXP-06) traps focus, Esc closes it and focus returns to "Allocation
// Structure…"; the Segmented view switch on TXP-07 moves with the arrow keys. Through the real
// routes on each screen's scenario, with axe and INV-1 to INV-5 after every step (harness).
import { expect, test } from "../harness";

// T-06-T69: both workspaces are the seed's entitlements now; no flag to turn on.
const FLAGS: string[] = [];
const RETURN = "/tax-returns/_returnId_";
const LIVE = "T-05-T69: full stack once T-05's slices are seeded on the stack";

test.describe("entity keyboard (T-05-T69)", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", LIVE);
  });

  test("TXP-11 grid: arrows move, Enter and F2 edit, Esc cancels, the address is announced", async ({
    journey,
  }) => {
    await journey.as("olivia-brandt", `${RETURN}/workpaper`, {
      scenario: "TXP-11:a",
      flags: FLAGS,
    });
    await journey.step("TXP-11 keyboard: H12 → I12 → I11", async (page) => {
      const grid = page.getByRole("grid").first();
      await grid.focus();
      await expect(grid).toBeFocused();
      await expect(page.getByText("05 Capital!H12").first()).toBeVisible();
      await page.keyboard.press("ArrowRight");
      await expect(page.getByText("05 Capital!I12").first()).toBeVisible();
      await page.keyboard.press("ArrowUp");
      await expect(page.getByText("05 Capital!I11").first()).toBeVisible();
      const active = await grid.getAttribute("aria-activedescendant");
      expect(active).toMatch(/I11$/u);
    });
    await journey.step("TXP-11 keyboard: Enter edits, Esc cancels; F2 edits", async (page) => {
      await page.keyboard.press("Enter");
      const editor = page.getByRole("textbox", { name: "Edit 05 Capital!I11" });
      await expect(editor).toBeFocused();
      await page.keyboard.press("Escape");
      await expect(editor).toHaveCount(0);
      await page.getByRole("grid").first().focus();
      await page.keyboard.press("F2");
      await expect(page.getByRole("textbox", { name: "Edit 05 Capital!I11" })).toBeFocused();
      await page.keyboard.press("Escape");
    });
  });

  test("TXP-06 O4: focus stays in the sheet, Esc closes it, focus returns to Allocation Structure…", async ({
    journey,
  }) => {
    await journey.as("samuel-ito", `${RETURN}/review/schedule-k`, {
      scenario: "TXP-06:a",
      flags: FLAGS,
    });
    await journey.step(
      "TXP-06 keyboard: the sheet traps focus and Esc returns it",
      async (page) => {
        const opener = page.getByRole("button", { name: "Allocation Structure…" });
        await opener.click();
        const sheet = page.getByRole("dialog").first();
        await expect(sheet).toBeVisible();
        for (let i = 0; i < 12; i += 1) {
          await page.keyboard.press("Tab");
          const inside = await sheet.evaluate((el) => el.contains(document.activeElement));
          expect(inside, `Tab ${String(i + 1)} stays in the sheet`).toBe(true);
        }
        await page.keyboard.press("Escape");
        await expect(sheet).toHaveCount(0);
        await expect(opener).toBeFocused();
      },
    );
  });

  test("TXP-07 Segmented: the arrow keys switch By partner and By movement", async ({
    journey,
  }) => {
    await journey.as("samuel-ito", `${RETURN}/review/capital`, {
      scenario: "TXP-07:a",
      flags: FLAGS,
    });
    await journey.step("TXP-07 keyboard: → By movement, ← By partner", async (page) => {
      const byPartner = page.getByRole("tab", { name: "By partner" });
      const byMovement = page.getByRole("tab", { name: "By movement" });
      await byPartner.focus();
      await page.keyboard.press("ArrowRight");
      await expect(byMovement).toHaveAttribute("aria-selected", "true");
      await expect(byMovement).toBeFocused();
      await page.keyboard.press("ArrowLeft");
      await expect(byPartner).toHaveAttribute("aria-selected", "true");
    });
  });
});
