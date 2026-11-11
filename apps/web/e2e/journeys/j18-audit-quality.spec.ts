// J18 audit quality, step 1 (A-05-T50) on fixtures: the late-remittance exception on EBP-04 is the
// anchor a finding starts from. Axe and INV-1 to INV-5 run through the harness.
import { DEMO_INSTANT, expect, test } from "../harness";
import { A07_LIVE, a07, noAgentDecision, onScreen } from "./a07-support";

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

// A-07-T50 (TASK-6820; A-07 §10 item 1): J18 steps 5 and 6 on the A-07 artboards in fixture mode:
// the EQR's concurrence (G6), the release (G8) and the archive lock (G9); after the lock a
// workpaper offers no edit and only a post-lock addition, which needs the partner.
test.describe("J18 G6 to G9 (A-07-T50)", () => {
  test("j18 5-6: G6 concurrence, release and archive lock; a locked workpaper refuses edits and only Post-lock addition is offered", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", A07_LIVE);
    await journey.as("thomas-whitcombe", a07("AUD-18", "c"));
    await journey.step("J18 step 5: G6 concurred by the EQR (AUD-18 c)", async (page) => {
      await onScreen(page, "AUD-18");
      await expect(page.getByText("G6 ✓").first()).toBeVisible();
    });
    await journey.as("margaret-okonkwo", a07("AUD-24", "d"));
    await journey.step("J18 step 5: G8 released by the partner (AUD-24 d)", async (page) => {
      await expect(
        page.getByText("Released Oct 9, 2026 · 10:07 AM · Margaret Okonkwo").first(),
      ).toBeVisible();
      await noAgentDecision(page);
    });
    await journey.as("margaret-okonkwo", a07("AUD-25", "c"));
    await journey.step("J18 step 6: G9 locked with its seal (AUD-25 c)", async (page) => {
      await expect(page.getByText("Locked · WORM").first()).toBeVisible();
    });
    await journey.as("marcus-delaney", a07("AUD-25", "d"));
    await journey.step(
      "J18 step 6: only a post-lock addition is offered (AUD-25 d)",
      async (page) => {
        await expect(page.getByText("+ Add after lock…").first()).toBeVisible();
        await expect(page.getByText("Addition logged").first()).toBeVisible();
        await expect(page.getByRole("button", { name: /^Edit/ })).toHaveCount(0);
        await expect(page.getByRole("button", { name: /^Sign off/ })).toHaveCount(0);
      },
    );
  });

  test("j18 6: an edit to a locked engagement is refused by the server (409 archived)", ({
    journey,
  }) => {
    // The refusal is the server's (archived_guard, A-07-T13; I-IMMUTABLE): only the full-stack
    // and staging projects reach it. The fixture project has no server to refuse.
    test.fixme(journey.project === "fixture", "the archived guard is the server's (full-stack)");
    test.fixme(journey.project !== "fixture", A07_LIVE);
  });
});
