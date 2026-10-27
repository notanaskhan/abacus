// J16 daily practice (P-01-T16 wrote steps 1-2 against the shell; G-01-T16 makes the ADM-01
// assertion live): Grace Holloway opens Firm settings from the firm pill and lands on the firm
// profile. The step runs on the harness (axe and INV-1 to INV-5 after it). In fixture mode the
// journey starts on the firm settings fixtures (`?screen=ADM-02&st=a`; DEC-457) and clicks through
// the real shell; the full stack and staging walk it after the batch deploy (G-01-T19).
// `firm_settings.v2` is retired (G-01-T17, DEC-594).
// P-01-T16 adds step 1 (Grace inside the toolbar) and the default-office half of step 2 (SHL-03 f);
// P-06-T25 adds step 5, the morning chase: Grace filters Binders to clients silent for 30 days and
// sends the Request Chaser's drafted follow-up (the agent drafts, a person sends; DEC-74), on
// BND-01's own scenario in the fixture project until `binders.engine` is on in E0 (P-06-T16).
import { DEMO_INSTANT, expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};

const LIVE = "binders.engine is off in E0; the BND-01 live swap is P-06-T16's";

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("J16 daily practice", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
  });

  test(
    "j16 2: Grace opens Firm settings from the firm pill (SHL-03a, ADM-01)",
    owner("G-01 · G-01-T16 fixture; full stack and staging after G-01-T17 · S11, Thu Apr 1, 2027"),
    async ({ journey }) => {
      test.fixme(journey.project !== "fixture", "walked full stack after the batch (G-01-T19)");
      await journey.as("grace-holloway", "/?screen=ADM-02&st=a", { clock: DEMO_INSTANT });
      await journey.step("J16 step 2: Firm settings from the firm pill", async (page) => {
        await page.getByRole("button", { name: "Brightwater Hale" }).first().click();
        const menu = page.getByRole("menu", { name: "Firm and profile" });
        await expect(menu).toBeVisible();
        await menu.getByRole("menuitem", { name: "Firm settings" }).click();
        await expect(page).toHaveURL(/\/settings\/general/);
        await expect(page.getByText("46 of 46 seats · 0 pending invites")).toBeVisible();
        await expect(page.getByRole("region", { name: "At a glance" })).toBeVisible();
      });
    },
  );

  test("j16 1: Grace signs in through hosted sign-in and lands inside the Accrued toolbar", async ({
    journey,
  }) => {
    await journey.as("grace-holloway", "/", { clock: DEMO_INSTANT });
    await journey.step("J16 step 1: Grace inside the toolbar (SHL-03a)", async (page) => {
      await expect(page.getByRole("navigation", { name: "Modules" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Brightwater Hale" })).toBeVisible();
    });
  });

  test("j16 2 (office): Grace sets Chicago as her default office (SHL-03f)", async ({
    journey,
  }) => {
    // SHL-03 f's /v1/me lists the firm's offices; the seed's carries none yet.
    await journey.as("grace-holloway", "/", { clock: DEMO_INSTANT, scenario: "SHL-03:f" });
    await journey.step("J16 step 2: Chicago as the default office (SHL-03f)", async (page) => {
      await page.getByRole("button", { name: "Brightwater Hale" }).click();
      await page.getByRole("menuitem", { name: "Default office filter" }).click();
      await page.getByRole("menuitemradio", { name: "Chicago" }).click();
      const menu = page.getByRole("menu", { name: "Firm and profile" });
      if (!(await menu.isVisible()))
        await page.getByRole("button", { name: "Brightwater Hale" }).click();
      await expect(menu.locator("[data-value='office']")).toHaveText("Chicago");
    });
  });

  test.describe("BND-01 steps", () => {
    test.beforeEach(({ journey }) => {
      test.fixme(journey.project !== "fixture", LIVE);
    });

    test("j16 5: Grace sends Request Chaser follow-ups from BND-01 and the agent sends nothing", async ({
      journey,
    }) => {
      await journey.as("grace-holloway", "/binders?client_activity=none_30_days", {
        scenario: "BND-01:b",
        flags: ["binders.engine"],
      });
      await journey.step("J16 step 5: Fenwick, silent since Aug 11 (BND-01b)", async (page) => {
        await expect(page.getByText("Fenwick Family Foundation").first()).toBeVisible();
      });
      await journey.step("J16 step 5: the Request Chaser's draft, not sent", async (page) => {
        await page.getByRole("button", { name: /^Send reminders?…$/ }).click();
        const sheet = page.getByRole("dialog", { name: "Send follow-ups · 1" });
        await expect(
          sheet.getByText("To Fenwick Family Foundation (portal contacts)"),
        ).toBeVisible();
        await expect(
          sheet.getByText(
            "Drafted by Accrued Agent (Request Chaser) · not sent · Reminder template (POR-20)",
          ),
        ).toBeVisible();
        await expect(sheet.getByText("Nothing is sent until you click Send.")).toBeVisible();
      });
      await journey.step("J16 step 5: Grace sends, a person's click", async (page) => {
        const sheet = page.getByRole("dialog", { name: "Send follow-ups · 1" });
        await sheet.getByRole("button", { name: "Send 1 follow-up" }).click();
        await expect(page.getByText(/^1 follow-up sent by /).first()).toBeVisible();
      });
    });
  });
});
