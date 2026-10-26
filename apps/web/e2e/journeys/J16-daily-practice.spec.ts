// J16 daily practice (P-01-T16 wrote steps 1-2 against the shell; G-01-T16 makes the ADM-01
// assertion live): Grace Holloway opens Firm settings from the firm pill and lands on the firm
// profile. The step runs on the harness (axe and INV-1 to INV-5 after it). ADM-01 sits behind
// `firm_settings.v2`, which E0 leaves off, so in fixture mode the journey starts on the firm
// settings fixtures (`?screen=ADM-02&st=a`, which turn the flag on; DEC-457) and clicks through the
// real shell; the full stack and staging walk it once E0 turns the flag on (G-01-T17, T19).
import { DEMO_INSTANT, expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};

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
      test.fixme(journey.project !== "fixture", "firm_settings.v2 is not on in E0 (G-01-T17)");
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
});
