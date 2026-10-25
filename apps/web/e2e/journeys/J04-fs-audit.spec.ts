// J04-fs-audit, PBC slice (F-04-T32; F-04.33; blueprint §7.4): Granite Peak Outdoor Supply's FY2026
// financial statement audit asks for a document, Luis Ferrante (Granite Peak's CFO) uploads it in
// the portal, the upload is scanned and screened, and the staff accept it or return it. The slice
// runs at the Sep 24 snapshot (F-04.18: Granite Peak's fieldwork), which the Pilot 0 sessions load.
// Walkable steps run on the harness in every project (axe and INV-1 to INV-5 after each step); a
// step whose screen or backend is still planned is `test.fixme` naming its owning epic, task and
// chapter 01 date (journey-e2e skill), never skipped or left out. Walkable on staging by M6 (Fri
// Mar 5, 2027). The portal is white-labelled: no portal step may show the product's name (INV-4).
import { expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
// The Sep 24 snapshot's instant (backend epochs.py: 2026-09-24 09:00 CT).
const SEP_24 = "2026-09-24T09:00:00-05:00";
const GRANITE_PEAK = "Granite Peak Outdoor Supply, Inc.";

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("J04-fs-audit PBC slice", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    // Hosted projects run only from the jobs that set their URL (F-04-T28; staging is not up yet).
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
  });

  test("J04 pbc 1: Luis Ferrante opens Granite Peak's portal sign-in (POR-01a)", async ({
    journey,
  }) => {
    await journey.as("luis-ferrante", "/sign-in", { clock: SEP_24 });
    await journey.step("J04 pbc step 1: portal sign-in as Luis Ferrante", async (page) => {
      await expect(
        page.getByRole("heading", { name: "Sign in to your client portal" }),
      ).toBeVisible();
      await expect(page.getByText(/accrued/i)).toHaveCount(0);
    });
  });

  test.fixme(
    "J04 pbc 2: Hannah Leclerc asks Granite Peak for the bank statements from the binder (BND-02, SHL-14)",
    owner("P-06 · P-06-T16 BND-02 fixture-to-live swap, binders.engine on · S6, Fri Jan 22, 2027"),
    async ({ journey }) => {
      await journey.as("hannah-leclerc", "/binders", { clock: SEP_24 });
      await journey.step("J04 pbc step 2: Granite Peak's binder", async (page) => {
        await expect(page.getByText(GRANITE_PEAK).first()).toBeVisible();
      });
    },
  );

  test.fixme(
    "J04 pbc 3: Luis Ferrante uploads the statement against the request (POR-03, POR-04)",
    owner("R-01 · R-01-T10 POR-03 drop target; R-01-T18 live /documents · S10, Fri Mar 19, 2027"),
    async ({ journey }) => {
      await journey.as("luis-ferrante", "/documents", { clock: SEP_24 });
    },
  );

  test.fixme(
    "J04 pbc 4: the upload is scanned and lands as Uploaded – needs review (POR-03c)",
    owner("R-01 · R-01-T10 drop with the scan's sorted state · S8, Fri Feb 19, 2027"),
    async ({ journey }) => {
      await journey.as("luis-ferrante", "/documents", { clock: SEP_24 });
    },
  );

  test.fixme(
    "J04 pbc 5: the screening shows its checks to Grace Holloway (SHL-20)",
    owner("P-06 · P-06-T22 SHL-20 states a-f on the screening aggregate · S8, Fri Feb 19, 2027"),
    async ({ journey }) => {
      await journey.as("grace-holloway", "/binders", { clock: SEP_24 });
    },
  );

  test.fixme(
    "J04 pbc 6: Grace accepts the statement, or returns it with a reason the client reads (SHL-20)",
    owner("P-06 · P-06-T22 SHL-20 accept and ReturnDialog · S8, Fri Feb 19, 2027"),
    async ({ journey }) => {
      await journey.as("grace-holloway", "/binders", { clock: SEP_24 });
    },
  );
});
