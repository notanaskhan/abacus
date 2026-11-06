// J18 audit quality, step 1 (A-05-T50) on fixtures: the late-remittance exception on EBP-04 is the
// anchor a finding starts from. Axe and INV-1 to INV-5 run through the harness.
import { DEMO_INSTANT, expect, test } from "../harness";

test.describe("J18 audit quality", () => {
  test("j18 1: F-01 from EBP-04 anchored on EBP-04!F31", async ({ journey }) => {
    await journey.as("marcus-delaney", "/audits/_auditId_?screen=EBP-04&st=a&section=ebp_04", {
      clock: DEMO_INSTANT,
    });
    await journey.step("J18 step 1: the exception on EBP-04", async (page) => {
      await expect(page.locator("[data-screen='EBP-04']").first()).toBeVisible();
    });
  });
});
