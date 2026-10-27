// P-07's gates and access (P-07-T53; P-07 §10 DoD 1): CLI-04's portal invite (INV-4), CLI-07's
// acceptance decision and CLI-08's confirmations as human-only gates (INV-1), ENG-05's blocked
// assignment, and J03 steps 1 and 2 (Margaret records Northwind's continuance; Ana Cruz's
// assignment waits on her independence until CLI-08 reads "All confirmed").
//
// The fixture project walks each step on the screen's own scenario through its live route
// (`?screen=`, DEC-457), with axe and INV-1 to INV-5 after every step. Full stack and staging walk
// the same steps once the demo seed carries these states and staging is up (STAGING_JOURNEYS off,
// F-04-T28); until then they are `test.fixme` with their owner (DEC-645).
import { expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const LIVE =
  "the demo seed does not carry CLI-04/07/08's states yet; full stack and staging walk with P-07-T62 (S14)";
const CONTACTS = "/clients/_clientId_/contacts";
const ACCEPTANCE = "/clients/_clientId_/acceptance/_engagementId_";
const INDEPENDENCE = "/clients/_clientId_/independence/_engagementId_";

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("P-07 gates and access", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
    test.fixme(journey.project !== "fixture", LIVE);
  });

  test("cli-04 b: Grace invites Harborline to the portal for its two delegated requests (INV-4)", async ({
    journey,
  }) => {
    await journey.as("grace-holloway", CONTACTS, { scenario: "CLI-04:a" });
    await journey.step("CLI-04 a: Northwind's contacts before the invite", async (page) => {
      await expect(page.getByText("3 active · 1 invited · 2 not invited").first()).toBeVisible();
      await expect(page.getByText("Harborline Trust Company").first()).toBeVisible();
    });
    await journey.as("grace-holloway", CONTACTS, { scenario: "CLI-04:c" });
    await journey.step(
      "CLI-04 c: Harborline invited, scoped to its delegated requests",
      async (page) => {
        await expect(page.getByText("3 active · 2 invited · 1 not invited").first()).toBeVisible();
      },
    );
  });

  test.fixme(
    "cli-04 b portal: Harborline sees only its two delegated requests (INV-4)",
    owner(
      "P-08 portal sign-in on staging: the invite's first sign-in walks full stack (P-07-T62, S14)",
    ),
    async () => {},
  );

  test("cli-07: only the engagement partner decides acceptance; the manager prepares (INV-1)", async ({
    journey,
  }) => {
    await journey.as("samuel-ito", ACCEPTANCE, { scenario: "CLI-07:b" });
    await journey.step("CLI-07 b: Samuel's draft is not ready for a decision", async (page) => {
      await expect(
        page.getByText("Not ready for decision — 1 manual check open").first(),
      ).toBeVisible();
    });
    await journey.as("daniel-reyes", ACCEPTANCE, { scenario: "CLI-07:a" });
    await journey.step(
      "CLI-07 a: Daniel, the engagement partner, holds the decision",
      async (page) => {
        await expect(page.getByText("Form 706 is required").first()).toBeVisible();
      },
    );
    await journey.as("daniel-reyes", ACCEPTANCE, { scenario: "CLI-07:d" });
    await journey.step("CLI-07 d: decided with conditions; the record is locked", async (page) => {
      await expect(page.getByText("Draft engagement letter →").first()).toBeVisible();
    });
  });

  test("cli-08: confirmations are each person's own; conclusion waits for all of them (INV-1)", async ({
    journey,
  }) => {
    await journey.as("ana-cruz", INDEPENDENCE, { scenario: "CLI-08:e" });
    await journey.step("CLI-08 e: Ana confirms her own independence", async (page) => {
      await expect(page.getByText("I am not a participant in the plan.").first()).toBeVisible();
    });
    await journey.as("margaret-okonkwo", INDEPENDENCE, { scenario: "CLI-08:f" });
    await journey.step("CLI-08 f: 5 of 5 confirmed; Margaret may conclude", async (page) => {
      await expect(page.getByText("5 of 5 confirmed").first()).toBeVisible();
    });
  });
});

test.describe("J03-ebp-audit (P-07's steps 1 and 2)", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
    test.fixme(journey.project !== "fixture", LIVE);
  });

  test("j03 1: Margaret records the continuance in CLI-07", async ({ journey }) => {
    // CLI-07's continuance artboard is Meridian's FY2026 (f); Northwind's continuance is the
    // demo seed's, walked full stack (P-07-T62).
    await journey.as("margaret-okonkwo", ACCEPTANCE, { scenario: "CLI-07:f" });
    await journey.step("J03 step 1: the continuance with its prior-year history", async (page) => {
      await expect(page.getByText("Prior-year history — one open item").first()).toBeVisible();
    });
  });

  test("j03 2: CLI-08 waits on Ana Cruz, then reads all confirmed (G2)", async ({ journey }) => {
    await journey.as("hannah-leclerc", INDEPENDENCE, { scenario: "CLI-08:a" });
    await journey.step("J03 step 2: 4 of 5 confirmed, Ana Cruz pending", async (page) => {
      await expect(page.getByText("4 of 5 confirmed").first()).toBeVisible();
    });
    await journey.as("margaret-okonkwo", INDEPENDENCE, { scenario: "CLI-08:f" });
    await journey.step("J03 step 2: all confirmed; G2 can be met", async (page) => {
      await expect(page.getByText("5 of 5 confirmed").first()).toBeVisible();
    });
  });

  test.fixme(
    "j03 2: ENG-05 refuses assigning Ana Cruz until she confirms",
    owner("ENG-05 has no route yet (manifest path null); P-07 · ENG-05's route wiring (S13)"),
    async () => {},
  );
});
