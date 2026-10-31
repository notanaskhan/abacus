// SIG-01 · Signatures hub and evidence drawer (N-02-T40; N-02 §10.1): every walkable state on the
// harness (axe serious/critical = 0 and INV-1 to INV-5 after each step). The Signatures area has
// no route yet (`nav-areas` routed false), so the fixture project walks the artboards in the
// /components gallery on the fake provider; the full stack, staging and the canary walk the hub
// with N-02-T42's M13 journeys.
import { expect, test } from "../harness";
import { M13, artboard, owner, skipUnhosted } from "./support";

test.describe("SIG-01 hub, full stack (N-02-T40)", () => {
  test.beforeEach(({ journey }) => {
    skipUnhosted(journey.project);
  });

  test("Grace reads the hub: out for signature, to send, completed and empty", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", M13);
    await journey.as("grace-holloway", artboard("SIG-01", "a"));
    await journey.step("SIG-01 a: E2 out, the drawer names the handwritten path", async (page) => {
      await expect(page.getByText(/Thomas & Irene Kowal/).first()).toBeVisible();
      await expect(page.getByText("Needs a handwritten signature").first()).toBeVisible();
      await expect(page.getByText(/Send new link at unlock/)).toHaveCount(0);
    });
    await journey.as("grace-holloway", artboard("SIG-01", "b"));
    await journey.step("SIG-01 b: two drafts to send", async (page) => {
      await expect(page.getByText(/Harborview Dental Properties, LP/).first()).toBeVisible();
    });
    await journey.as("grace-holloway", artboard("SIG-01", "c"));
    await journey.step("SIG-01 c: completed, last 30 days", async (page) => {
      await expect(page.getByText(/Summit Line Logistics, Inc\./).first()).toBeVisible();
    });
    await journey.as("grace-holloway", artboard("SIG-01", "e"));
    await journey.step("SIG-01 e: the declined variant", async (page) => {
      await expect(page.getByText(/Noor & Adam Farouk/).first()).toBeVisible();
    });
  });

  test(
    "Grace reminds three signers from a preview; nothing sends before Send (SIG-01 f)",
    owner("N-02 · N-02-T28 remind (live) and N-02-T42 hosted walk · S21, Fri Aug 20, 2027"),
    async ({ journey }) => {
      test.fixme(journey.project !== "fixture", M13);
      await journey.as("grace-holloway", artboard("SIG-01", "f"));
      await journey.step("SIG-01 f: three selected, Remind 3…", async (page) => {
        await expect(page.getByText(/3 selected/).first()).toBeVisible();
        await expect(page.getByRole("button", { name: /Remind 3/ }).first()).toBeVisible();
      });
    },
  );
});
