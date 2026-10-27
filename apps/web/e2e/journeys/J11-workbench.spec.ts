// J11 workbench (P-01-T16; blueprint §7.11): a3, a finished scheduled run notifies Hannah
// Leclerc in the bell drawer (SHL-04, the R2 "Trigger run finished" rows). Fixture project only:
// the run records and their notifications are W-02's, so the other projects keep it fixme. Each
// step runs axe and INV-1 to INV-5.
import { expect, test } from "../harness";

test.describe("J11", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", "scheduled runs and their notifications are W-02's");
  });

  test("j11 a3: a finished scheduled run notifies Hannah", async ({ journey }) => {
    await journey.as("hannah-leclerc", "/", { scenario: "SHL-04:g" });
    await journey.step("J11 step a3: the run-finished row in the drawer", async (page) => {
      await page.getByRole("button", { name: /^Notifications/ }).click();
      await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
      await expect(page.getByText("Unrecorded liabilities tester finished")).toBeVisible();
    });
  });
});
