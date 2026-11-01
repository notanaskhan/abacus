// A-03's journey slices (A-03-T19; A-03 §10 "Journeys advanced"; blueprint §7): j03 11 Marcus draws
// 25 with seed 0x5E2A91, Hannah approves, 125 item requests go out (100 POR-03, 25 POR-14); j04 2
// Granite Peak's 128 accounts mapped by rule and confirmed, then changed after sign-off by TB
// version 2; j22 2 (sampling slice) 1,912 disbursements tie and 40 items (24 + 16) are drawn with
// seed 0x7C31B4; j20 3 (contract slice) one entity's mapping set by rule. In the fixture project
// each step opens its screen's own artboard (`/components/screens/<ID>?st=<state>`, the screen's
// scenario and persona); axe and INV-1 to INV-5 run after every step. The full-stack and hosted
// walks wait for A-03's live swaps on staging and are `test.fixme` naming their owner, never
// skipped or left out; j20 3 is API-level on a Harlow & Pike-shaped fixture entity, so it has no
// fixture-project step.
import { expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const LIVE_OWNER =
  "A-03-T19 staging walk once AUD-11 and AUD-31 swap to live (A-03 §10); human: the staging run";
const CONTRACT_OWNER =
  "A-03-T19 full stack: j20 3's API walk on the Harlow & Pike-shaped entity (A-03-T16 seed); the group UI is A-09's";

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

function artboard(id: string, state: string): string {
  return `/components/screens/${id}?st=${state}`;
}

test.describe("A-03 journeys: sampling and the trial balance mapping", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
    test.fixme(journey.project !== "fixture", LIVE_OWNER);
  });

  test(
    "j03 11: Marcus draws 25 with seed 0x5E2A91, Hannah approves, 125 item requests go out (100 POR-03, 25 POR-14)",
    owner(LIVE_OWNER),
    async ({ journey }) => {
      await journey.as("marcus-delaney", artboard("AUD-11", "b"));
      await journey.step(
        "j03 step 11: Version 2 prepared, not yet approved (AUD-11 b)",
        async (page) => {
          // INV-1: Generate stays off until a manager approves.
          await expect(
            page.getByRole("button", { name: /Generate item requests/ }),
          ).toBeDisabled();
        },
      );
      await journey.as("marcus-delaney", artboard("AUD-11", "a"));
      await journey.step(
        "j03 step 11: Version 2 approved by Hannah, 25 items (AUD-11 a)",
        async (page) => {
          await expect(page.getByText("0x5E2A91").first()).toBeVisible();
        },
      );
      await journey.as("marcus-delaney", artboard("AUD-11", "c"));
      await journey.step("j03 step 11: the Generate sheet's preview (AUD-11 c)", async (page) => {
        // ADR-050: the counts are the server's preview, never summed in the browser.
        await expect(page.getByText("125 requests · 100 to POR-03 · 25 to POR-14")).toBeVisible();
      });
      await journey.as("marcus-delaney", artboard("SHL-14", "c"));
      await journey.step(
        "j03 step 11: the sample wave in the composer (SHL-14 c)",
        async (page) => {
          await expect(page.getByText("Create 25 requests").first()).toBeVisible();
        },
      );
    },
  );

  test(
    "j04 2: Granite Peak's 128 accounts are mapped by rule and confirmed Prepared · CD",
    owner(LIVE_OWNER),
    async ({ journey }) => {
      await journey.as("caleb-dunn", artboard("AUD-31", "f"));
      await journey.step(
        "j04 step 2: 128 of 128 mapped and confirmed (AUD-31 f)",
        async (page) => {
          await expect(page.getByText("128 of 128").first()).toBeVisible();
          await expect(
            page.getByText("Mapping confirmed by Caleb Dunn on Sep 11 · 128 accounts"),
          ).toBeVisible();
        },
      );
      await journey.as("caleb-dunn", artboard("AUD-31", "e2"));
      await journey.step(
        "j04 step 2: TB version 2 changes it after sign-off (AUD-31 e′)",
        async (page) => {
          await expect(page.getByText("Changed after sign-off").first()).toBeVisible();
        },
      );
    },
  );

  test(
    "j22 2 (sampling slice): 1,912 disbursements tie to the bank account and 40 items (24 + 16) are drawn with seed 0x7C31B4 totalling 3,698,700",
    owner(LIVE_OWNER),
    async ({ journey }) => {
      await journey.as("simone-baptiste", artboard("AUD-11", "f"));
      await journey.step(
        "j22 step 2: the ledger population and its strata (AUD-11 f)",
        async (page) => {
          await expect(page.getByText("1,912 payments").first()).toBeVisible();
          await expect(page.getByText("24 + 16 = 40").first()).toBeVisible();
          await expect(page.getByText("0x7C31B4").first()).toBeVisible();
        },
      );
    },
  );

  test.fixme(
    "j20 3 (contract slice): one entity's mapping set by rule; editing 1460 to PP&E › Deposits on equipment makes PP&E tie at 8,400,000",
    owner(CONTRACT_OWNER),
    async ({ journey }) => {
      await journey.as("caleb-dunn", "/audits");
    },
  );
});
