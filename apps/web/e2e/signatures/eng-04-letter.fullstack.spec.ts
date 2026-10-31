// ENG-04 · Engagement letter composer (N-02-T40; N-02 §10.1), ENG-02's Letter & terms tab. The
// fixture project walks its artboards (the tab's states need ENG-02's record around them); the
// hosted projects need the seeded engagement's id and the letter routes live (N-02-T35), so they
// walk with N-02-T42's M13 journeys.
import { expect, test } from "../harness";
import { M13, artboard, skipUnhosted } from "./support";

test.describe("ENG-04 letter, full stack (N-02-T40)", () => {
  test.beforeEach(({ journey }) => {
    skipUnhosted(journey.project);
  });

  test("Daniel's Ridgeline letter: approved, then sent with 0 of 2 signed", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", M13);
    await journey.as("daniel-reyes", artboard("ENG-04", "a"));
    await journey.step(
      "ENG-04 a: the template, the approval, two non-standard clauses",
      async (page) => {
        await expect(page.getByText("BH Tax Advisory Letter v4").first()).toBeVisible();
        await expect(page.getByText("Partner approved").first()).toBeVisible();
      },
    );
    await journey.as("daniel-reyes", artboard("ENG-04", "c"));
    await journey.step("ENG-04 c: read-only, 0 of 2 signed, View envelope", async (page) => {
      await expect(page.getByText("Sent · 0 of 2 signed").first()).toBeVisible();
      await expect(page.getByRole("button", { name: "View envelope ›" })).toBeVisible();
    });
  });

  test("the signed Copperleaf letter is locked (ENG-04 d)", async ({ journey }) => {
    test.fixme(journey.project !== "fixture", M13);
    await journey.as("daniel-reyes", artboard("ENG-04", "d"));
    await journey.step("ENG-04 d: signed and locked", async (page) => {
      await expect(page.getByText("Signed").first()).toBeVisible();
    });
  });
});
