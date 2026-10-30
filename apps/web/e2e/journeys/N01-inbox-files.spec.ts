// N-01's journey legs (N-01-T27; INB-01, INB-02, FIL-01): the firm inbox and the files browser
// in the fixture project, with INV-1 to INV-5 and axe after every step (the harness). Steps whose
// screen or backend is still planned are `test.fixme` naming their owner, never skipped. The
// figures are the seed's (src/fixtures/seed/__tests__/n01t27-inbox.foot.test.ts foots them
// independently): 23 waiting · 4 unmatched, and 21 after Grace's two filings.
import { expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const E0 = "2026-09-14T09:24:00-05:00";

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("N-01 inbox and files legs", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
  });

  test(
    "j16 6a: Grace opens the firm inbox: 23 waiting · 4 unmatched (INB-01 a)",
    owner("N-01 · N-01-T27 · S18"),
    async ({ journey }) => {
      test.fixme(journey.project !== "fixture", "walked full stack after the S18 batch deploy");
      await journey.as("grace-holloway", "/inbox", { clock: E0, scenario: "INB-01:a" });
      await journey.step("j16 step 6a: the inbox summary and its threads", async (page) => {
        await expect(page.getByText("23 waiting · 4 unmatched")).toBeVisible();
        await expect(page.getByText(/Re: 2025 tax documents/).first()).toBeVisible();
      });
    },
  );

  test(
    "j16 10: after triage the inbox reads 21 waiting (INB-01 d)",
    owner("N-01 · N-01-T27 · S18"),
    async ({ journey }) => {
      test.fixme(journey.project !== "fixture", "walked full stack after the S18 batch deploy");
      await journey.as("grace-holloway", "/inbox", { clock: E0, scenario: "INB-01:d" });
      await journey.step("j16 step 10: two files filed, 21 waiting", async (page) => {
        await expect(page.getByText("21 waiting · 4 unmatched")).toBeVisible();
      });
    },
  );

  test(
    "j06 4: Olivia opens Ridgeline's files and the statements foot (FIL-01 a)",
    owner("N-01 · N-01-T27 · S18"),
    async ({ journey }) => {
      test.fixme(journey.project !== "fixture", "walked full stack after the S18 batch deploy");
      await journey.as("olivia-brandt", "/files", { clock: E0, scenario: "FIL-01:a" });
      await journey.step("j06 step 4: the files browser lists the documents", async (page) => {
        await expect(page.getByRole("main")).toBeVisible();
        await expect(page.getByText("512,400").first()).toBeVisible();
      });
    },
  );

  test.fixme(
    "j09 1b: the intake leg files an emailed document to its request (INB-02)",
    owner("N-01 · INB-02 is planned (no route) until N-01-T23's mount · S19"),
    async ({ journey }) => {
      await journey.as("grace-holloway", "/inbox", { clock: E0 });
    },
  );

  test.fixme(
    "j12 3c: Claire uploads in the portal, then withdraws the upload (with R-01)",
    owner("N-01 with R-01 · the portal withdrawal is behind evidence.withdrawal · S19"),
    async ({ journey }) => {
      await journey.as("claire-feld", "/documents", { clock: E0 });
    },
  );

  test.fixme(
    "inbox regression: a staff-logged email lands once, attributed to its person",
    owner("N-01 · the staff-logged path needs the mail sink on the full stack · S19"),
    async ({ journey }) => {
      await journey.as("grace-holloway", "/inbox", { clock: E0 });
    },
  );
});
