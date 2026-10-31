// KNW-03 program editor walked in the app (K-01-T17; K-01 §3.4, §3.5; AC4.1, AC4.2, AC5.1): a
// citation lands on BH-EBP-110 step 4 lit (a, b), Hannah Leclerc's Draft v4 keeps every mandatory
// step locked to the QM owner (c), and the version exports to Excel. Every step runs axe and
// INV-1 to INV-5; no control here approves or publishes (INV-1: the draft is submitted, KNW-02
// approves).
//
// The row names `apps/web/e2e/knowledge/`; it lives under journeys/ beside knw-01-catalog so the
// harness projects pick it up (DEC-457, DEC-1663). Fixture mode opens KNW-03's own artboards on
// the gallery route (`/components/screens/KNW-03?st=`, which installs the artboard's scenario and
// the route's search params, as R01's journey does), so the spec never reaches into src for ids.
// Full stack and staging walk the real route once the demo firm has the methodology slice and the
// flag (K-01 flag plan; STAGING_JOURNEYS is off).
import { expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const LIVE =
  "methodology.programs is off in E0 and the methodology slice is opt-in; full stack and staging walk KNW-03 once the demo firm has both (K-01 flag plan, STAGING_JOURNEYS)";
const CLOCK = "2026-09-14T14:30:00-05:00";
const screen = (state: string): string => `/components/screens/KNW-03?st=${state}`;
const LOCK_TIP = "Only the QM owner can remove or unlock mandatory steps.";

test.describe("KNW-03 program editor", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
    test.fixme(journey.project !== "fixture", LIVE);
  });

  test("knw-03 a, b: a citation lands on step 4 lit and the popover quotes it", async ({
    journey,
  }) => {
    await journey.as("margaret-okonkwo", screen("a"), { clock: CLOCK });
    await journey.step("KNW-03 a: step 4 lit, 16 steps and 8 mandatory", async (page) => {
      const lit = page.locator("tr[data-step][data-lit]");
      await expect(lit).toHaveCount(1);
      await expect(lit).toHaveAttribute("data-step", "4");
      await expect(page.getByText("16 steps · 8 mandatory").first()).toBeVisible();
      await expect(page.getByRole("button", { name: /^(Publish|Approve)/u })).toHaveCount(0);
    });
    await journey.as("margaret-okonkwo", screen("b"), { clock: CLOCK });
    await journey.step("KNW-03 b: the SHL-07 popover names the program", async (page) => {
      await expect(
        page.getByText("BH-EBP-110: General Planning Procedures").first(),
      ).toBeVisible();
      await expect(page.getByText("1 citation").first()).toBeVisible();
    });
  });

  test("knw-03 c: Hannah's Draft v4, mandatory steps locked to the QM owner", async ({
    journey,
  }) => {
    await journey.as("hannah-leclerc", screen("c"), { clock: CLOCK });
    await journey.step("KNW-03 c: the draft banner, + Step, and the lock", async (page) => {
      await expect(
        page.getByText("Draft v4 — changes apply to new engagements after approval in KNW-02."),
      ).toBeVisible();
      await expect(page.getByRole("button", { name: "+ Step" })).toBeEnabled();
      await expect(page.locator(`tr[data-step="1"] [aria-label="${LOCK_TIP}"]`)).toHaveCount(1);
      await expect(page.getByRole("button", { name: "Remove step 1" })).toBeDisabled();
      await expect(page.getByRole("textbox", { name: "Step 1 text" })).toHaveCount(0);
      await expect(page.getByRole("textbox", { name: "Step 3 text" })).toBeVisible();
      await expect(page.getByRole("button", { name: /^(Publish|Approve)/u })).toHaveCount(0);
    });
  });

  test("knw-03 a: Open in Excel downloads the version", async ({ journey }) => {
    await journey.as("margaret-okonkwo", screen("a"), { clock: CLOCK });
    await journey.step("KNW-03 a: the program's workbook", async (page) => {
      const button = page.getByRole("button", { name: "Open in Excel" });
      await expect(button).toBeEnabled();
      const [download] = await Promise.all([page.waitForEvent("download"), button.click()]);
      expect(download.suggestedFilename()).toMatch(/\.xlsx$/u);
    });
  });
});
