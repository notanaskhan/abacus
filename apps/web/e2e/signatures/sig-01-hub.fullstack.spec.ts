// SIG-01 · Signatures hub and evidence drawer (N-02-T40; N-02 §10.1): every walkable state on the
// harness (axe serious/critical = 0 and INV-1 to INV-5 after each step). The fixture project walks
// the artboards in the /components gallery on the fake provider. The full stack walks the routed
// hub (`/signatures`, N-02-T42) on the `signatures` seed slice (TASK-7820): the same rows, reached
// by the hub's own tabs and row drawer. Staging and the canary wait on the hosted sign-in (M13).
import { expect, test } from "../harness";
import { M13, NO_DECLINED, artboard, hubTab, owner, skipUnhosted } from "./support";

test.describe("SIG-01 hub, full stack (N-02-T40)", () => {
  test.beforeEach(({ journey }) => {
    skipUnhosted(journey.project);
  });

  test("Grace reads the hub: out for signature, to send, completed and empty", async ({
    journey,
  }) => {
    test.fixme(journey.project === "staging" || journey.project === "canary", M13);
    const live = journey.project !== "fixture";
    await journey.as("grace-holloway", live ? "/signatures" : artboard("SIG-01", "a"));
    if (live) {
      // E2's row opens the evidence drawer (the artboard opens with it).
      const page = journey.page;
      await page
        .getByText(/Thomas & Irene Kowal/)
        .first()
        .click();
    }
    await journey.step("SIG-01 a: E2 out, the drawer names the handwritten path", async (page) => {
      await expect(page.getByText(/Thomas & Irene Kowal/).first()).toBeVisible();
      await expect(page.getByText("Needs a handwritten signature").first()).toBeVisible();
      await expect(page.getByText(/Send new link at unlock/)).toHaveCount(0);
    });
    if (live) {
      // The evidence drawer is modal: close it before the hub's tabs take a click again.
      await journey.page.getByRole("button", { name: "Close" }).click();
      await hubTab(journey.page, "To send");
    } else await journey.as("grace-holloway", artboard("SIG-01", "b"));
    await journey.step("SIG-01 b: drafts to send", async (page) => {
      await expect(page.getByText(/Harborview Dental Properties, LP/).first()).toBeVisible();
    });
    if (live) await hubTab(journey.page, "Completed");
    else await journey.as("grace-holloway", artboard("SIG-01", "c"));
    await journey.step("SIG-01 c: completed, last 30 days", async (page) => {
      await expect(page.getByText(/Summit Line Logistics, Inc\./).first()).toBeVisible();
    });
    if (live) {
      test.info().annotations.push({ type: "fixme", description: `SIG-01 e: ${NO_DECLINED}` });
    } else {
      // SIG-01 e is a variant the seed does not record (no envelope is declined on Sep 14).
      await journey.as("grace-holloway", artboard("SIG-01", "e"));
      await journey.step("SIG-01 e: the declined variant", async (page) => {
        await expect(page.getByText(/Noor & Adam Farouk/).first()).toBeVisible();
      });
    }
  });

  test(
    "Grace reminds three signers from a preview; nothing sends before Send (SIG-01 f)",
    owner("N-02 · N-02-T28 remind (live) and N-02-T42 hosted walk · S21, Fri Aug 20, 2027"),
    async ({ journey }) => {
      test.fixme(journey.project === "staging" || journey.project === "canary", M13);
      const live = journey.project !== "fixture";
      await journey.as("grace-holloway", live ? "/signatures" : artboard("SIG-01", "f"));
      if (live) {
        // Three out-for-signature envelopes the seed numbers as the handoff does (E1, E3, E5),
        // picked by their own labelled checkboxes; nothing is sent here.
        for (const n of ["E1", "E3", "E5"]) {
          await journey.page.getByRole("checkbox", { name: `Select ${n}`, exact: true }).check();
        }
      }
      await journey.step("SIG-01 f: three selected, Remind 3…", async (page) => {
        await expect(page.getByText(/3 selected/).first()).toBeVisible();
        await expect(page.getByRole("button", { name: /Remind 3/ }).first()).toBeVisible();
      });
    },
  );
});
