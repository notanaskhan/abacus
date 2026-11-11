// J05 step S (K-02-T19; K-02 §1): SSARS 27 early adoption is off in KNW-04 h, so Copperleaf's
// periods ending before Dec 15, 2026 are prepared under AR-C 70. Each step runs axe and INV-1 to
// INV-5 (journey harness). The CLS consumer of the switch is C-01's; this step reads the standard.
import { expect, test } from "../harness";
import { owner as r02Owner } from "./r02-support";
import { A08_AUD26, owner as a07Owner } from "./a07-support";

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

// A-06-T35 (TASK-6121): J05 step 4, the preparation engagement's statements; fixme until A-08's
// AUD-26 runs full stack (S35) and the preparation scenario lands on AUD-20.
test.describe("J05 completion (A-06-T35)", () => {
  test.fixme("j05 4: the prepared statements carry the AR-C 70 legend (AUD-20)", async ({
    journey,
  }) => {
    await journey.as("priya-raman", "/audits/_auditId_/fs-disclosure", { scenario: "AUD-20:a" });
  });
});

// R-02-T23 (R-02 §5.6): variant P needs Carla Juniper's preparation statements on POR-08, which no
// provider registers yet (A-08) and R-02-T19's fixtures do not draw.
test.describe("J05 · R-02 approvals", () => {
  test.fixme(
    "j05 P: Carla Juniper approves the preparation statements in POR-08",
    r02Owner(
      "A-08 · registers the preparation-statements approval provider; then a Carla fixture",
    ),
    async () => {},
  );
});

// A-07-T50 (TASK-6820): J05 step 6, the review report mode (AUD-23 e), waits for AUD-26's SSARS
// reports (A-08); ADR-079 forbids a skip without an issue, so it is fixme naming its owner.
test.describe("J05 report mode (A-07-T50)", () => {
  test.fixme("j05 6: review report mode", a07Owner(A08_AUD26), async () => {});
});
