// J23 audit partner's morning (N-02-T42; N-02 §3.10, §10.1, M13): j23 3, Margaret Okonkwo
// countersigns and the engagement's G3 is met; nobody else countersigns for her. The fixture walk
// uses the built artboards: SIG-01 c (Completed) and ENG-04 d (signed and countersigned, locked).
// The E14 Granite Peak walk runs on staging (M13); the hosted runs are fixme until then.
import { expect, test } from "../harness";
import { M13, artboard, skipUnhosted } from "../signatures/support";
import { P05_LIVE, nothingBlocks, p05 } from "./p05-support";

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

// P-05-T15 (TASK-7311; P-05 §10 item 1): J23 step 6 on SHL-18 and SHL-17 in fixture mode. Steps 1-5
// stay fixme until I-02, K-04 and A-11.
test.describe("J23 collaboration (P-05-T15)", () => {
  test("j23 6: comment with @Hannah Leclerc and a to-do for Marcus, neither blocks sign-off", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", P05_LIVE);
    await journey.as("margaret-okonkwo", p05("SHL-18", "a", "margaret-okonkwo"));
    await journey.step(
      "J23 step 6: the comment mentions Hannah Leclerc (SHL-18 a)",
      async (page) => {
        await expect(page.locator("[data-screen='SHL-18']").first()).toBeVisible();
        await expect(
          page.getByText("Hannah Leclerc notified in Accrued and by email · 12:35 PM").first(),
        ).toBeVisible();
        await nothingBlocks(page);
      },
    );
    await journey.as("margaret-okonkwo", p05("SHL-17", "a", "margaret-okonkwo"));
    await journey.step("J23 step 6: the to-do for Marcus Delaney (SHL-17 a)", async (page) => {
      await expect(page.locator("[data-screen='SHL-17']").first()).toBeVisible();
      await expect(page.getByText("Marcus Delaney").first()).toBeVisible();
      await expect(page.getByRole("button", { name: /^Sign off/ })).toHaveCount(0);
      await nothingBlocks(page);
    });
  });
});
