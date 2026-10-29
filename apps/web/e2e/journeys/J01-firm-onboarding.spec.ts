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

// ADM-06 (G-02-T16) sits behind this flag, which E0 leaves off (G-02-T21).
const SECURITY_CENTER = ["security_center.v1"];
const AI_POLICY = ["ai_policy.v1"];
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
    owner("G-01 · G-01-T07 ADM-01 (flag retired, G-01-T17) · walked on staging by M8"),
    async ({ journey }) => {
      // ADM-01 is built on fixtures (G-01-T07) and served to every firm since G-01-T17 retired
      // `firm_settings.v2` (DEC-594); the full stack walks it after the batch deploy (G-01-T19).
      test.fixme(journey.project !== "fixture", "walked full stack after the batch (G-01-T19)");
      await journey.as("margaret-okonkwo", "/settings/general", { clock: DEMO_INSTANT });
      await journey.step("J01 step 1: the firm profile as Margaret Okonkwo", async (page) => {
        await expect(page.getByText("Brightwater Hale").first()).toBeVisible();
      });
    },
  );

  test(
    "J01 2: Felix signs in with an email code and a second factor (SHL-06c)",
    owner("P-01 · P-01-T16 on the WorkOS fake (full stack) and staging · M5, Fri Jan 22, 2027"),
    async ({ journey }) => {
      // The hosted sign-in is the identity provider's page (the WorkOS fake on the full stack),
      // never the SPA's: the fixture project presets a session, so it has no sign-in to walk.
      test.fixme(
        journey.project === "fixture",
        "fixture mode presets the session (no hosted page)",
      );
      await journey.as("felix-andersen", "/", { clock: DEMO_INSTANT });
      await journey.step("J01 step 2: Felix is signed in, inside the toolbar", async (page) => {
        await expect(page.getByRole("navigation", { name: "Modules" })).toBeVisible();
        await expect(page.getByRole("button", { name: "Brightwater Hale" })).toBeVisible();
      });
    },
  );

  test(
    "J01 3: Grace reaches Firm settings from the firm pill (SHL-03a)",
    owner("P-01 · P-01-T16 · M5, Fri Jan 22, 2027"),
    async ({ journey }) => {
      // SHL-03 a: Grace's capabilities hold the admin section (the seed answers none yet).
      await journey.as("grace-holloway", "/", { clock: DEMO_INSTANT, scenario: "SHL-03:a" });
      await journey.step("J01 step 3: the firm pill's menu (SHL-03a)", async (page) => {
        await page.getByRole("button", { name: "Brightwater Hale" }).click();
        await expect(page.getByRole("menu", { name: "Firm and profile" })).toBeVisible();
      });
      await journey.step("J01 step 3: Firm settings opens", async (page) => {
        await page.getByRole("menuitem", { name: "Firm settings" }).click();
        // Firm settings is the methodology admin until ADM-01 replaces it (G-01; its assertion
        // stays fixme until then), then /settings.
        await expect(page).toHaveURL(/\/(admin\/methodology|settings)\b/);
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

  // G-01-T16 (DEC-457): the nightly load does not seed the people slice ADM-02 and ADM-03 need, so
  // in fixture mode the step opens the real route on the screen's own scenario (`?screen=&st=`);
  // the full stack and staging walk it after the batch deploy (G-01-T19). `firm_settings.v2` is
  // retired (G-01-T17, DEC-594).
  test(
    "J01 3: Grace creates offices Chicago, Denver and New York (ADM-03)",
    owner("G-01 · G-01-T16 fixture; full stack and staging after G-01-T17 · S11, Thu Apr 1, 2027"),
    async ({ journey }) => {
      test.fixme(journey.project !== "fixture", "the people slice is not in E0");
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
      test.fixme(journey.project !== "fixture", "the people slice is not in E0");
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

  test(
    "j01 2: Felix enforces Microsoft SSO and MFA",
    owner(
      "G-02 · G-02-T21 fixture; full stack once E0 turns security_center.v1 on, staging and the canary after the batch deploy · M7, Fri Apr 16, 2027",
    ),
    async ({ journey }) => {
      // ADM-06 sits behind `security_center.v1`, which E0 leaves off: in fixture mode each step
      // opens the real route on the screen's own scenario (DEC-457).
      test.fixme(journey.project !== "fixture", "security_center.v1 is not on in E0");
      await journey.as("felix-andersen", "/settings/security?screen=ADM-06&st=a", {
        clock: DEMO_INSTANT,
        flags: SECURITY_CENTER,
      });
      await journey.step("j01 step 2: SSO and MFA enforced as Felix Andersen", async (page) => {
        const signIn = page.getByRole("heading", { name: "Firm sign-in" });
        await expect(signIn).toBeVisible();
        await expect(page.getByText("Microsoft Entra ID (SSO)").first()).toBeVisible();
        await expect(page.getByText("Enforced · 46 of 46 enrolled").first()).toBeVisible();
        await expect(
          page.getByRole("switch", { name: "Require SSO for all firm users" }),
        ).toBeVisible();
        await expect(page.getByText("Day 4 of 30 · notify by Oct 10 if ≥ 500")).toBeVisible();
      });
      await journey.as("felix-andersen", "/settings/security?screen=ADM-06&st=d", {
        clock: DEMO_INSTANT,
        flags: SECURITY_CENTER,
      });
      await journey.step("j01 step 2: INC-2026-005 and its two-person decision", async (page) => {
        const drawer = page.getByRole("dialog");
        await expect(drawer.getByRole("progressbar", { name: "Day 4 of 30" })).toBeVisible();
        await expect(
          drawer.getByRole("button", { name: "Close as not reportable…" }),
        ).toBeVisible();
        await expect(drawer.getByRole("button", { name: "Start notification…" })).toBeVisible();
      });
      await journey.as("felix-andersen", "/settings/security?screen=ADM-06&st=h", {
        clock: DEMO_INSTANT,
        flags: SECURITY_CENTER,
      });
      await journey.step("j01 step 2: the WISP and the Pub 4557 evidence", async (page) => {
        await expect(
          page.getByText(/BH WISP v4 \(IRS Pub 5708 format\) · approved by Margaret Okonkwo/),
        ).toBeVisible();
        await expect(page.getByRole("button", { name: "Export WISP pack" })).toBeVisible();
      });
    },
  );

  test(
    "J01 4: Margaret requests v4 of the AI policy and Daniel approves it (ADM-04)",
    owner(
      "G-02 · G-02-T26 fixture; full stack once E0 turns ai_policy.v1 on, staging after the batch deploy · S14, Fri May 14, 2027",
    ),
    async ({ journey }) => {
      // ADM-04 sits behind `ai_policy.v1`, which E0 leaves off: in fixture mode each step opens
      // the real route on the screen's own scenario (DEC-457). The agent principal's refusal at
      // publish and approve is the server's (G-02-T22's suite), not a fixture's.
      test.fixme(journey.project !== "fixture", "ai_policy.v1 is not on in E0");
      await journey.as("margaret-okonkwo", "/settings/ai-policy?screen=ADM-04&st=a", {
        clock: DEMO_INSTANT,
        flags: AI_POLICY,
      });
      await journey.step(
        "j01 step 4: v3 reviewed, twelve gates, nothing to save",
        async (page) => {
          await expect(page.getByText(/^BH AI policy v3 · published /)).toBeVisible();
          await expect(page.getByText("5. Proposed AJE within threshold")).toBeVisible();
          await expect(page.getByRole("button", { name: "Save as v4…" })).toBeDisabled();
        },
      );
      await journey.as("margaret-okonkwo", "/settings/ai-policy?screen=ADM-04&st=b", {
        clock: DEMO_INSTANT,
        flags: AI_POLICY,
      });
      await journey.step(
        "j01 step 4: Margaret requests v4 with Daniel as approver",
        async (page) => {
          await page.getByRole("button", { name: "Save as v4…" }).click();
          const sheet = page.getByRole("dialog");
          await expect(sheet.getByText("Override tolerance 8% → 6%")).toBeVisible();
          await expect(sheet.getByText("Daniel Reyes")).toBeVisible();
          await expect(sheet.getByText("Margaret Okonkwo")).toHaveCount(0);
        },
      );
      await journey.as("daniel-reyes", "/settings/ai-policy?screen=ADM-04&st=awaiting", {
        clock: DEMO_INSTANT,
        flags: AI_POLICY,
      });
      await journey.step("j01 step 4: Daniel Reyes approves v4", async (page) => {
        await expect(page.getByText("Awaiting approval · Daniel Reyes")).toBeVisible();
        await expect(page.getByRole("button", { name: "Approve v4" })).toBeVisible();
      });
      await journey.as("hannah-leclerc", "/settings/ai-policy?screen=ADM-04&st=e", {
        clock: DEMO_INSTANT,
        flags: AI_POLICY,
      });
      await journey.step("j01 step 4: a manager reads the policy only", async (page) => {
        await expect(page.getByText("Only partners can change the AI policy.")).toBeVisible();
        await expect(page.getByRole("button", { name: /^Save as v/ })).toHaveCount(0);
      });
    },
  );

  test.fixme(
    "J01 5: the client portal's branding is set and previewed (ADM-10)",
    owner("R-01 · R-01-T28 ADM-10 with the live preview column · S12, Fri Apr 16, 2027"),
    async ({ journey }) => {
      await journey.as("margaret-okonkwo", "/settings/general", { clock: DEMO_INSTANT });
    },
  );

  // K-01-T11 (DEC-902): j01 5w walks KNW-02's workbook slice, which is K-01-T07's (not built:
  // KNW-02 has no screen yet). The service half (import lands Needs review, the agent's approve is
  // refused, Margaret approves, v2 is superseded) is proven by K-01-T06 and K-01-T09's suites.
  test.fixme(
    "J01 5w: Margaret imports BH EBP v3, the agent's approve is refused, she approves and v2 is superseded (KNW-02)",
    owner("K-01 · K-01-T07 KNW-02 workbook slice on the T3 Prepare frame · S12, Fri Apr 16, 2027"),
    async ({ journey }) => {
      await journey.as("margaret-okonkwo", "/knowledge", { clock: DEMO_INSTANT });
    },
  );
});
