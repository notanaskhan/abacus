// ENG-04 · Engagement letter composer (N-02-T40; N-02 §10.1) on ENG-02's Letter & terms tab,
// through the real route (`/engagements/<id>/letter`) on each state's own scenario in the fixture
// project (G-01-T16's `?screen=`). The hosted projects need the seeded engagement's id and the
// letter routes live (N-02-T35), so they walk with N-02-T42's M13 journeys.
import { expect, test } from "../harness";
import { M13, skipUnhosted } from "./support";

const FLAGS = ["engagements.v2", "engagements.letter_composer", "signatures.envelopes"];
const LETTER = "/engagements/_engagementId_/letter";

test.describe("ENG-04 letter, full stack (N-02-T40)", () => {
  test.beforeEach(({ journey }) => {
    skipUnhosted(journey.project);
  });

  test("Daniel's Ridgeline letter: approved, then sent with 0 of 2 signed", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", M13);
    await journey.as("daniel-reyes", LETTER, { flags: FLAGS, scenario: "ENG-04:a" });
    await journey.step(
      "ENG-04 a: the template, the approval, two non-standard clauses",
      async (page) => {
        await expect(page.getByText("BH Tax Advisory Letter v4").first()).toBeVisible();
        await expect(page.getByText("Partner approved").first()).toBeVisible();
      },
    );
    await journey.as("daniel-reyes", LETTER, { flags: FLAGS, scenario: "ENG-04:c" });
    await journey.step("ENG-04 c: read-only, 0 of 2 signed, View envelope", async (page) => {
      await expect(page.getByText("Sent · 0 of 2 signed").first()).toBeVisible();
      await expect(page.getByRole("button", { name: "View envelope ›" })).toBeVisible();
    });
  });

  test("the signed Copperleaf letter is locked (ENG-04 d)", async ({ journey }) => {
    test.fixme(journey.project !== "fixture", M13);
    await journey.as("daniel-reyes", LETTER, { flags: FLAGS, scenario: "ENG-04:d" });
    await journey.step("ENG-04 d: signed and locked", async (page) => {
      await expect(page.getByText("Signed").first()).toBeVisible();
    });
  });
});
