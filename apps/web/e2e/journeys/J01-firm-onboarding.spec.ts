// J01-core, firm onboarding (F-04-T32; F-04.33; blueprint §7.1): Brightwater Hale's firm admin
// signs in, reviews the firm profile, sets offices, teams and walls, invites the staff and turns on
// the client portal. A skeleton for M8 (Fri May 28, 2027): the walkable step runs on the harness in
// every project (axe and INV-1 to INV-5 after it); every other step is `test.fixme` naming its
// owning epic, task and chapter 01 date (journey-e2e skill), never skipped or left out.
import { DEMO_INSTANT, expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};

// ADM-02f's clock (fixtures/scenarios/ADM-02.ts CLOCK_F): Mon Jan 5, 2026, 10:12 AM CT.
const JAN_5 = "2026-01-05T10:12:00-06:00";

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("J01-core firm onboarding", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    // Hosted projects run only from the jobs that set their URL (F-04-T28; staging is not up yet).
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
  });

  test(
    "J01 1: Margaret Okonkwo opens the firm's settings (ADM-01)",
    owner("G-01 · G-01-T07 ADM-01 live behind firm_settings.v2 · walked on staging by M8"),
    async ({ journey }) => {
      // ADM-01 is built on fixtures (G-01-T07); the full stack serves it once E0 turns
      // firm_settings.v2 on for the firm.
      test.fixme(journey.project !== "fixture", "firm_settings.v2 is not on in E0 (G-01-T07)");
      await journey.as("margaret-okonkwo", "/settings/general", { clock: DEMO_INSTANT });
      await journey.step("J01 step 1: the firm profile as Margaret Okonkwo", async (page) => {
        await expect(page.getByText("Brightwater Hale").first()).toBeVisible();
      });
    },
  );

  test.fixme(
    "J01 2: Margaret reviews users and roles and invites a staff member (ADM-02)",
    owner("G-01 · G-01-T10 ADM-02 users table and role templates · S8, Fri Feb 19, 2027"),
    async ({ journey }) => {
      await journey.as("margaret-okonkwo", "/settings/general", { clock: DEMO_INSTANT });
    },
  );

  // G-01-T16 (DEC-457): ADM-02 and ADM-03 sit behind `firm_settings.v2`, which E0 leaves off and
  // the nightly load does not seed with the people slice, so in fixture mode the step opens the
  // real route on the screen's own scenario (`?screen=&st=`); the full stack and staging walk it
  // once E0 turns the flag on (G-01-T17) and the batch deploy carries it (G-01-T19).
  test(
    "J01 3: Grace creates offices Chicago, Denver and New York (ADM-03)",
    owner("G-01 · G-01-T16 fixture; full stack and staging after G-01-T17 · S11, Thu Apr 1, 2027"),
    async ({ journey }) => {
      test.fixme(
        journey.project !== "fixture",
        "firm_settings.v2 and the people slice are not in E0",
      );
      await journey.as("grace-holloway", "/settings/offices?screen=ADM-03&st=a", {
        clock: DEMO_INSTANT,
      });
      await journey.step(
        "J01 step 3: offices, teams and seats as Grace Holloway",
        async (page) => {
          await expect(page.getByText("Chicago · HQ").first()).toBeVisible();
          await expect(page.getByText("Denver").first()).toBeVisible();
          await expect(page.getByText("New York").first()).toBeVisible();
          await expect(page.getByText("46 seats · 224 returns").first()).toBeVisible();
        },
      );
    },
  );

  test(
    "J01 3: Grace invites the seeded staff, and a 47th invite shows seats full (ADM-02c)",
    owner("G-01 · G-01-T16 fixture; full stack and staging after G-01-T17 · S11, Thu Apr 1, 2027"),
    async ({ journey }) => {
      test.fixme(
        journey.project !== "fixture",
        "firm_settings.v2 and the people slice are not in E0",
      );
      await journey.as("grace-holloway", "/settings/people?screen=ADM-02&st=c", {
        clock: DEMO_INSTANT,
      });
      await journey.step("J01 step 3: the invite with every seat held", async (page) => {
        const invite = page.getByRole("dialog", { name: "Invite user" });
        await expect(invite).toBeVisible();
        await expect(
          page.getByText("All 46 seats are assigned. Add seats or deactivate a user first."),
        ).toBeVisible();
      });
    },
  );

  test(
    "J01 3f: on Jan 5, 2026 Lena Park's invite reads pending and expires in 14 days (ADM-02f)",
    owner("G-01 · G-01-T16 fixture; full stack and staging after G-01-T17 · S11, Thu Apr 1, 2027"),
    async ({ journey }) => {
      test.fixme(journey.project !== "fixture", "the pending-invite snapshot is fixture-only");
      await journey.as("grace-holloway", "/settings/people?screen=ADM-02&st=f", {
        clock: JAN_5,
      });
      await journey.step("J01 step 3f: Lena Park's pending invite", async (page) => {
        await expect(page.getByText("Invite pending · expires Jan 19").first()).toBeVisible();
      });
    },
  );

  test.fixme(
    "J01 4: the AI policy and approval gates are reviewed (ADM-04)",
    owner("G-02 · G-02-T25 ADM-04 at /settings/ai-policy · S14, Fri May 14, 2027"),
    async ({ journey }) => {
      await journey.as("margaret-okonkwo", "/settings/general", { clock: DEMO_INSTANT });
    },
  );

  test.fixme(
    "J01 5: the client portal's branding is set and previewed (ADM-10)",
    owner("R-01 · R-01-T28 ADM-10 with the live preview column · S12, Fri Apr 16, 2027"),
    async ({ journey }) => {
      await journey.as("margaret-okonkwo", "/settings/general", { clock: DEMO_INSTANT });
    },
  );
});
