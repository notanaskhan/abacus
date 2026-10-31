// J05 step S (K-02-T19; K-02 §1): SSARS 27 early adoption is off in KNW-04 h, so Copperleaf's
// periods ending before Dec 15, 2026 are prepared under AR-C 70. Each step runs axe and INV-1 to
// INV-5 (journey harness). The CLS consumer of the switch is C-01's; this step reads the standard.
import { expect, test } from "../harness";

test.describe("J05", () => {
  test("j05 S: SSARS 27 early adoption off, so AR-C 70 for Copperleaf (KNW-04 h)", async ({
    journey,
  }) => {
    test.fixme(
      journey.project !== "fixture",
      "KNW-04 is fixture-first until the K-02 batch deploy",
    );
    await journey.as("priya-raman", "/knowledge/standards?section=ssars_cas", {
      scenario: "KNW-04:h",
      flags: ["knowledge.firm_standards"],
    });
    await journey.step("J05 step S: SSARS & CAS", async (page) => {
      await expect(
        page.getByText("Early-adopt SSARS 27 for CAS monthly statements").first(),
      ).toBeVisible();
      await expect(page.getByText(/prepared under AR-C 70/u).first()).toBeVisible();
    });
  });
});
