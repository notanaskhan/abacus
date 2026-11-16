// J07 trust 1041 (T-02-T32; T-07-T30; T-07 §2 "Journeys advanced"): the Calloway Family Trust
// from the governing instrument to released K-1s. Steps 1 to 7 walk TXT-01 to TXT-03 on their
// artboards (the fixture project opens `/components/screens/<ID>?st=<state>`); step 8, the
// beneficiary K-1s released, Nora Calloway sees only her own K-1 and not Theo's or the trust
// return (POR-13 a). Axe and INV-1 to INV-5 run after every step. Staging waits on T-07's live
// swaps and is `test.fixme` naming its owner.
import { expect, test } from "../harness";

const OWNER = "T-02-T32: T-02's screens live on staging and the canary, Thu Aug 12, 2027";

function artboard(id: string, state: string): string {
  return `/components/screens/${id}?st=${state}`;
}

test.describe("J07", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", OWNER);
  });

  test("j07 1 to 3: the instrument, then the trust calculation", async ({ journey }) => {
    await journey.as("samuel-ito", artboard("TXT-01", "a"));
    await journey.step("J07 step 1: the governing instrument (TXT-01a)", async (page) => {
      await expect(page.getByText(/Calloway/).first()).toBeVisible();
    });
    await journey.as("samuel-ito", artboard("TXT-02", "a"));
    await journey.step("J07 step 3: the trust calculation (TXT-02a)", async (page) => {
      await expect(page.getByText(/Calloway/).first()).toBeVisible();
    });
  });

  test("j07 5 to 7: allocation foots, release gated, then released", async ({ journey }) => {
    await journey.as("samuel-ito", artboard("TXT-03", "a"));
    await journey.step("J07 step 5: the allocation foots (TXT-03a)", async (page) => {
      await expect(page.getByText("240,000").first()).toBeVisible();
      // [H] gate: release waits on final approval and the trustee's 8879-F.
      await expect(page.getByRole("button", { name: "Release K-1s…" })).toBeDisabled();
    });
    await journey.as("samuel-ito", artboard("TXT-03", "b"));
    await journey.step("J07 step 7: K-1s released to the portal (TXT-03b)", async (page) => {
      await expect(page.getByText("Released Sep 28").first()).toBeVisible();
      await expect(page.getByRole("button", { name: "Resend…" })).toBeVisible();
    });
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
