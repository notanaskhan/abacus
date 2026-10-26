// J15-advisory (blueprint §7.15): an advisory project. R-01-T21 creates this file with step 5
// (Tallgrass Cost Engineering, a third party, uploads in its POR-14 room) in fixture mode only,
// because the project and its delegations arrive with PRJ-01 (T-09). No fixture scenario carries
// Tallgrass's room yet and none may be invented, so the step stays `test.fixme` naming the task
// whose seed-derived fixtures bring it (journey-e2e skill); it runs in the fixture project once
// they land, and full stack after T-09.
import { DEMO_INSTANT, test } from "../harness";

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
