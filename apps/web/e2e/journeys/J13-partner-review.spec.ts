// J13 partner review (P-01-T16; blueprint §7.13): the chrome of the partner's morning. Daniel
// Reyes signs in, sees the bell's dot and opens the notifications drawer (SHL-01, SHL-04). The rows
// are fixture until the P-04 producers land. Each step runs axe and INV-1 to INV-5.
import { DEMO_INSTANT, expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};

test.describe("J13", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
  });

  test("j13 1-2 chrome: Daniel signs in, sees the bell dot and opens the notifications drawer", async ({
    journey,
  }) => {
    // The rows are SHL-04 a's fixture (the P-04 producers write them later); the fixture project
    // lays that scenario over the seed, the full stack reads the bell's own answer.
    await journey.as("daniel-reyes", "/", { clock: DEMO_INSTANT, scenario: "SHL-04:a" });
    await journey.step(
      "J13 step 1: Daniel inside the toolbar, the bell lit (SHL-01)",
      async (page) => {
        await expect(page.getByRole("navigation", { name: "Modules" })).toBeVisible();
        await expect(page.getByRole("button", { name: "Notifications, unread" })).toBeVisible();
      },
    );
    await journey.step("J13 step 2: the notifications drawer (SHL-04)", async (page) => {
      await page.getByRole("button", { name: "Notifications, unread" }).click();
      await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
    });
  });
});

// T-02-T32 (T-02 §2): j13 7-8, the K-1 release clears the draft chips on the Feld intake and Daniel
// gives the Feld final approval (TAX-03 d, TAX-02 e), on the screens' artboards in the fixture
// project; staging waits on T-02's live swaps.
test.describe("J13 · T-02 release and final approval", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(
      journey.project !== "fixture",
      "T-02-T32: T-02's screens live on staging and the canary, Thu Aug 12, 2027",
    );
  });

  test("j13 7-8: the release clears the draft chips and Daniel approves the Feld 1040", async ({
    journey,
  }) => {
    await journey.as("daniel-reyes", "/components/screens/TAX-03?st=d");
    await journey.step(
      "J13 step 7: the draft chip gives way to the final (TAX-03d)",
      async (page) => {
        await expect(page.getByText("Released Sep 15").first()).toBeVisible();
      },
    );
    await journey.as("daniel-reyes", "/components/screens/TAX-02?st=e");
    await journey.step("J13 step 8: Feld final approval unblocked (TAX-02e)", async (page) => {
      await expect(page.locator("[data-artboard='e']")).toBeVisible();
      await expect(page.getByText(/final approval is blocked until/)).toHaveCount(0);
    });
  });
});
