// J02-audit-core (F-04-T26; F-04.11, F-04.33; blueprint §7.2 through the audit lens): a client,
// then an engagement, gates G1 to G3 recorded, a binder and a request. Walkable steps run on the
// harness in every project (axe and INV-1 to INV-5 after each step); a step whose screen is still
// planned is `test.fixme` naming its owning epic, task and chapter 01 date, never skipped or left
// out (journey-e2e skill). The full stack loads E0 with `--holdout fairhaven_ebp`, so the
// Fairhaven Foods 401(k) Plan is created here (CLI-06 → CLI-07 → ENG-03) and CLI-01 reads 183
// clients before and 184 after (F-04.11).
import { DEMO_INSTANT, expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const WALLED = "Ashford Manufacturing Co."; // ADM-03's wall for Lena Park (INV-3)

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("J02-audit-core", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    // Hosted projects run only from the jobs that set their URL (F-04-T28; staging is not up yet).
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
  });

  // `/clients` answers with CLI-01 once `clients.v2` is on for the firm (P-07-T10); until E0 turns
  // it on, the route keeps the earlier client list, which this step walks under the same checks.
  test("J02 1: Grace Holloway finds the client in the Clients index (CLI-01)", async ({
    journey,
  }) => {
    await journey.as("grace-holloway", "/clients", { clock: DEMO_INSTANT });
    await journey.step("J02 step 1: the Clients index as Grace Holloway", async (page) => {
      await expect(page.getByRole("heading", { name: "Clients", exact: true })).toBeVisible();
      await expect(page.getByText("Northwind Robotics, Inc.").first()).toBeVisible();
    });
  });

  test("J02 1 (wall): Lena Park's Clients index leaves out the walled client (CLI-01c, INV-3)", async ({
    journey,
  }) => {
    await journey.as("lena-park", "/clients", { clock: DEMO_INSTANT });
    await journey.step(
      "J02 step 1, walled: the Clients index as Lena Park",
      async (page) => {
        await expect(page.getByRole("heading", { name: "Clients", exact: true })).toBeVisible();
        await expect(page.getByText(WALLED)).toHaveCount(0);
      },
      { outOfScope: [WALLED] },
    );
  });

  test.fixme(
    "J02 2: Grace creates the Fairhaven Foods 401(k) Plan client and its conflict check runs (CLI-06)",
    owner("P-07 · P-07-T49 CLI-06 single intake · S11, Fri Apr 2, 2027"),
    async ({ journey }) => {
      await journey.as("grace-holloway", "/clients", { clock: DEMO_INSTANT });
    },
  );

  test.fixme(
    "J02 3: the partner records acceptance for Fairhaven (CLI-07, G1)",
    owner("P-07 · P-07-T46 CLI-07 acceptance and continuance · S10, Fri Mar 19, 2027"),
    async ({ journey }) => {
      await journey.as("margaret-okonkwo", "/clients", { clock: DEMO_INSTANT });
    },
  );

  test.fixme(
    "J02 4: Hannah Leclerc creates the PY2025 EBP audit in the wizard (ENG-03)",
    owner("P-07 · P-07-T21 ENG-03 wizard core, audit family · S6, Fri Jan 22, 2027"),
    async ({ journey }) => {
      await journey.as("hannah-leclerc", "/engagements", { clock: DEMO_INSTANT });
    },
  );

  test.fixme(
    "J02 5: the engagement record shows G1 to G3 recorded (ENG-02b)",
    owner("P-07 · P-07-T20 ENG-02 record core with gate rows · S6, Fri Jan 22, 2027"),
    async ({ journey }) => {
      await journey.as("hannah-leclerc", "/engagements", { clock: DEMO_INSTANT });
    },
  );

  // BND-01 is built on fixtures, but E0 does not turn `binders.engine` on for the firm (neither the
  // fixture capabilities nor `make seed-demo`), so `/binders` shows the flag-off state until the
  // swap that turns it on.
  test.fixme(
    "J02 6: Grace Holloway finds the new binder in the Binders index (BND-01)",
    owner("P-06 · P-06-T16 BND-01 fixture-to-live swap, binders.engine on · S6, Fri Jan 22, 2027"),
    async ({ journey }) => {
      await journey.as("grace-holloway", "/binders", { clock: DEMO_INSTANT });
      await journey.step("J02 step 6: the Binders index as Grace Holloway", async (page) => {
        await expect(page.getByRole("heading", { name: "Binders", exact: true })).toBeVisible();
      });
    },
  );

  test.fixme(
    "J02 7: the binder publishes its first request to the client (BND-02)",
    owner("P-06 · P-06-T16 BND-02 fixture-to-live swap · S6, Fri Jan 22, 2027"),
    async ({ journey }) => {
      await journey.as("hannah-leclerc", "/binders", { clock: DEMO_INSTANT });
    },
  );
});
