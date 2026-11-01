// J23 audit partner's morning (N-02-T42; N-02 §3.10, §10.1, M13): j23 3, Margaret Okonkwo
// countersigns and the engagement's G3 is met; nobody else countersigns for her. The fixture walk
// uses the built artboards: SIG-01 c (Completed) and ENG-04 d (signed and countersigned, locked).
// The E14 Granite Peak walk runs on staging (M13); the hosted runs are fixme until then.
import { expect, test } from "../harness";
import { M13, artboard, skipUnhosted } from "../signatures/support";

test.describe("J23", () => {
  test.beforeEach(({ journey }) => {
    skipUnhosted(journey.project);
    test.fixme(journey.project !== "fixture", M13);
  });

  test("j23 3: Margaret countersigns and G3 is met", async ({ journey }) => {
    await journey.as("margaret-okonkwo", artboard("SIG-01", "c"));
    await journey.step("j23 3: the completed envelopes (SIG-01 c)", async (page) => {
      await expect(page.getByRole("tab", { name: /Completed/, selected: true })).toBeVisible();
    });
    await journey.as("margaret-okonkwo", artboard("ENG-04", "d"));
    await journey.step("j23 3: signed and countersigned, locked (ENG-04 d)", async (page) => {
      await expect(page.getByText(/countersigned by /).first()).toBeVisible();
    });
  });
});
