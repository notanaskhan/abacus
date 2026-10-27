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
