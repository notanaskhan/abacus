// J17 practice economics (I-01-T25; I-01 §2): the journey's P0 core is HOME-01, its only P0 screen
// (chapter 01 §1.5.1 dates it S35, Fri Mar 3, 2028). Margaret Okonkwo's Home: her four waiting
// items (2 decisions, 2 approvals & sends) read the same number in the pane header, the summary
// line and the Approvals badge. Fixture mode lays HOME-01 b over the seed; staging reads the live
// counts after the batch deploy.
import { DEMO_INSTANT, expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("J17 practice economics", () => {
  test.beforeEach(({ journey }) => {
    test.skip(
      journey.project === "staging" && process.env.ABACUS_STAGING_URL === undefined,
      "ABACUS_STAGING_URL is not set",
    );
  });

  test(
    "j17 0: Margaret's Home tiles and counts tie (P0 core)",
    owner("I-01 · I-01-T25 · S35, Fri Mar 3, 2028"),
    async ({ journey }) => {
      // TASK-7813: HOME-01 b's four gates are the design's at E0; on the scenario timeline none is
      // open at 9:24 AM (Northwind's materiality is proposed at 10:30 AM and Granite Peak's at
      // 10:12 AM by the review and completion slices), and Fairhaven Foods' letter is held out of
      // the nightly seed (HOLDOUT=fairhaven_ebp), so the full stack's queue is empty.
      test.fixme(
        journey.project === "fullstack",
        "HOME-01 b's gates are not open at E0 on the scenario timeline; Fairhaven is held out",
      );
      await journey.as("margaret-okonkwo", "/", { clock: DEMO_INSTANT, scenario: "HOME-01:b" });
      await journey.step(
        "J17 0: one count on the header, the summary and the badge",
        async (page) => {
          // The pane and its scroll region share the name (layout/pane.tsx): the pane itself.
          const pane = page.getByRole("region", { name: "Waiting on you" }).first();
          await expect(pane).toBeVisible();
          await expect(pane.getByText("2 decisions")).toBeVisible();
          await expect(pane.getByText("2 approvals & sends")).toBeVisible();
          await expect(page.getByRole("tab", { name: /Approvals/u })).toContainText("4");
        },
      );
    },
  );
});
