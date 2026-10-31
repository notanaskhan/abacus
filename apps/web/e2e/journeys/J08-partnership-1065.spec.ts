// J08 partnership 1065 (T-02-T32; T-02 §2 "Journeys advanced"): j08 12, Olivia shares the Ridgeline
// drafts with the Feld and Shah 1040s (TXP-12 A4), and j08 16, Samuel releases five K-1s with K-3s
// on Sep 15 at 10:30 AM (TXP-12 A5 → B); the Pell Street Ventures member sees only Pell Street's
// package (POR-13 c) and Meera finds her K-1 under role union (POR-13 f). Firm steps open the
// screen's artboard; portal steps walk /k1s on POR-13's own states. Staging is `test.fixme`.
import { expect, test } from "../harness";

const OWNER = "T-02-T32: T-02's screens live on staging and the canary, Thu Aug 12, 2027";

function artboard(id: string, state: string): string {
  return `/components/screens/${id}?st=${state}`;
}

test.describe("J08", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", OWNER);
  });

  test("j08 12: Olivia shares drafts with the Feld and Shah 1040s", async ({ journey }) => {
    await journey.as("olivia-brandt", artboard("TXP-12", "a4"));
    await journey.step("J08 step 12: drafts shared (TXP-12 A4)", async (page) => {
      await expect(
        page.getByText("Drafts block final approval of the receiving return.").first(),
      ).toBeVisible();
    });
  });

  test("j08 16: Samuel releases five K-1s; each member sees only their own", async ({
    journey,
  }) => {
    await journey.as("samuel-ito", artboard("TXP-12", "a5"));
    await journey.step("J08 step 16: release ready (TXP-12 A5)", async (page) => {
      await expect(
        page
          .getByText("Portal · My K-1s (POR-13), with an invite email to each recipient")
          .first(),
      ).toBeVisible();
    });
    await journey.as("samuel-ito", artboard("TXP-12", "b"));
    await journey.step("J08 step 16: released, one invite bounced (TXP-12 B)", async (page) => {
      await expect(page.getByText("Invite email bounced — update address").first()).toBeVisible();
    });
    await journey.as("pell-street-member", "/k1s", {
      scenario: "POR-13:c",
      clock: "2026-09-15T09:24:00-05:00",
    });
    await journey.step(
      "J08 step 16: Pell Street Ventures' own package (POR-13c)",
      async (page) => {
        await expect(page.getByText("400,270").first()).toBeVisible();
        await expect(page.getByText(/Pell Street II/)).toHaveCount(0);
        await expect(page.getByText(/Accrued/)).toHaveCount(0);
      },
    );
    await journey.as("meera-shah", "/k1s", { scenario: "POR-13:f" });
    await journey.step("J08 step 16: Meera under role union (POR-13f)", async (page) => {
      await expect(
        page.getByText("Your K-1s are in Deliverables › My K-1s").first(),
      ).toBeVisible();
      await expect(page.getByText(/Accrued/)).toHaveCount(0);
    });
  });
});
