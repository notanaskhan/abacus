// R-01's journey steps (R-01-T32; R-01 §2; blueprint §7): j16 4 Grace edits, tests and publishes
// Reminder v4 (POR-20 a → j → k → l), j12 1 a Reminder from the published template reaches the
// sink with one dark button and no amounts, and j02's invitation from the database template. In
// the fixture project j16 4 walks POR-20's artboards (axe and INV-1 to INV-5 after each step); the
// sink and the database template need the full stack and are `test.fixme` there until R-01's live
// swap reaches staging. The M8 walk of j12 core on the production canary runs only in the canary
// project. Client email never shows the product's name (INV-4).
import { expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const LIVE_OWNER =
  "R-01-T21/T25/T27/T28 live on staging (POR-20, ADM-10, the sink); staging steps and the j12-core canary walk by M8, Fri May 28, 2027";

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("R-01 journeys: the firm's email templates", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
  });

  test(
    "j16 4: Grace edits, tests and publishes Reminder v4",
    owner(LIVE_OWNER),
    async ({ journey }) => {
      test.fixme(journey.project !== "fixture", LIVE_OWNER);
      for (const [state, label] of [
        ["a", "Reminder v3 published, a v4 draft saved (POR-20 a)"],
        ["j", "Send test… to Grace's own address, sample Claire Feld (POR-20 j)"],
        ["k", "the test sent: one [Test] message to Grace (POR-20 k)"],
        ["l", "v4 published by Grace, v3 retired (POR-20 l)"],
      ] as const) {
        await journey.as("grace-holloway", `/components/screens/POR-20?st=${state}`);
        await journey.step(`j16 step 4: ${label}`, async (page) => {
          await expect(page.locator(`[data-artboard='${state}']`)).toBeVisible();
        });
      }
    },
  );

  test(
    "j12 1: a Reminder from the published template reaches the sink",
    owner(LIVE_OWNER),
    async ({ journey }) => {
      test.fixme(true, LIVE_OWNER);
      await journey.as("claire-feld", "/");
    },
  );

  test(
    "j02: the invitation comes from the database template",
    owner(LIVE_OWNER),
    async ({ journey }) => {
      test.fixme(true, LIVE_OWNER);
      await journey.as("grace-holloway", "/");
    },
  );

  test("M8: j12 core on the production canary", owner(LIVE_OWNER), async ({ journey }) => {
    test.skip(journey.project !== "canary", "the canary walk runs only in the canary project");
    test.fixme(true, LIVE_OWNER);
    await journey.as("claire-feld", "/");
  });
});
