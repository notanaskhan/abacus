// J07 trust 1041 (T-02-T32; T-02 §2 "Journeys advanced"): j07 8, the Calloway beneficiary K-1s
// released; Nora Calloway sees only her own K-1 and not Theo's or the trust return (POR-13 a). In
// the fixture project Nora walks /k1s on POR-13's own state; axe and INV-1 to INV-5 run after each
// step. Staging waits on T-02's live swaps and is `test.fixme` naming its owner.
import { expect, test } from "../harness";

const OWNER = "T-02-T32: T-02's screens live on staging and the canary, Thu Aug 12, 2027";

test.describe("J07", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", OWNER);
  });

  test("j07 8: Nora sees only Nora's K-1 and not Theo's or the trust return", async ({
    journey,
  }) => {
    await journey.as("nora-calloway", "/k1s", {
      scenario: "POR-13:a",
      clock: "2026-09-29T18:40:00-05:00",
    });
    await journey.step("J07 step 8: Nora's released K-1 (POR-13a)", async (page) => {
      await expect(page.getByText("160,000").first()).toBeVisible();
      await expect(page.getByText(/Theo/)).toHaveCount(0);
      // Her own Schedule K-1 (Form 1041), one package, and never the trust's return.
      await expect(page.getByRole("heading", { name: /Schedule K-1 \(Form 1041\)$/ })).toHaveCount(
        1,
      );
      await expect(page.getByText(/Form 1041 return|U\.S\. Income Tax Return/)).toHaveCount(0);
      await expect(page.getByText(/Accrued/)).toHaveCount(0);
    });
  });
});
