// J15-advisory (blueprint §7.15): an advisory project. R-01-T21 creates this file with step 5
// (Tallgrass Cost Engineering, a third party, uploads in its POR-14 room) in fixture mode only,
// because the project and its delegations arrive with PRJ-01 (T-09). No fixture scenario carries
// Tallgrass's room yet and none may be invented, so the step stays `test.fixme` naming the task
// whose seed-derived fixtures bring it (journey-e2e skill); it runs in the fixture project once
// they land, and full stack after T-09.
import { DEMO_INSTANT, expect, test } from "../harness";
import { M13, artboard } from "../signatures/support";

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("J15-advisory (R-01's portal step)", () => {
  test.fixme(
    "J15 5: Tallgrass Cost Engineering uploads in its room (POR-14), fixture mode only",
    owner("T-09 · T-09-T03 PRJ-01 seed-derived fixtures · S66, Fri May 11, 2029"),
    async ({ journey }) => {
      // Tallgrass's contact joins the harness personas with T-09's fixtures; until then the room's
      // path is all this step can name.
      await journey.page.clock.setFixedTime(new Date(DEMO_INSTANT));
      await journey.page.goto("/requests");
    },
  );
});

// N-02-T40 (N-02 §10.1): j15 4 on the harness: Daniel's Ridgeline letter (ENG-04 a → c on its
// route), the builder's countersigner (SIG-02 e) and Owen's Sign area (POR-06). The hosted
// projects walk it with N-02-T42's M13 journeys.
test.describe("J15 signatures (N-02-T40)", () => {
  const FLAGS = ["engagements.v2", "engagements.letter_composer", "signatures.envelopes"];

  test("j15 4: Daniel sends the Ridgeline letter, Owen signs and Daniel countersigns (G3)", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", M13);
    await journey.as("daniel-reyes", "/engagements/_engagementId_/letter", {
      flags: FLAGS,
      scenario: "ENG-04:a",
    });
    await journey.step("j15 4: the approved Ridgeline letter (ENG-04 a)", async (page) => {
      await expect(page.getByText("Partner approved").first()).toBeVisible();
    });
    await journey.as("grace-holloway", artboard("SIG-02", "e"));
    await journey.step(
      "j15 4: the envelope, Owen then Daniel's countersignature (SIG-02 e)",
      async (page) => {
        await expect(page.getByText("1 · Owen Calder").first()).toBeVisible();
        await expect(page.getByText("2 · Daniel Reyes").first()).toBeVisible();
      },
    );
    await journey.as("owen-calder", "/sign", { scenario: "POR-06:list" });
    await journey.step("j15 4: Owen's Sign area (POR-06)", async (page) => {
      await expect(page.getByRole("heading", { name: /Sign/ }).first()).toBeVisible();
    });
  });
});
