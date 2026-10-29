// ENG/CLI core (P-07-T22; M5): the P-07 screens built on fixtures walked end to end in the app,
// each step with axe and INV-1 to INV-5 (journey harness): the Clients index (CLI-01), a client's
// record (CLI-02), the Engagements index (ENG-01) and an engagement's record with its gates
// (ENG-02b). The fixture project walks them; the other projects keep these fixme until the live
// walk is recorded (the flags themselves retired with P-07-T59).
import { DEMO_INSTANT, expect, test } from "../harness";

const NORTHWIND = "Northwind Robotics, Inc.";
const NORTHWIND_EBP = "PY2025 EBP Audit"; // ENG-02b: the Northwind Robotics 401(k) Plan audit
const LIVE =
  "clients.v2 and engagements.v2 are off in E0; the live routes are P-07-T15's and T16's";

test.describe("ENG/CLI core", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", LIVE);
  });

  test("CLI-01 to CLI-02: Grace Holloway opens Northwind's record from its row", async ({
    journey,
  }) => {
    await journey.as("grace-holloway", "/clients", { clock: DEMO_INSTANT });
    await journey.step("CLI-01: the Clients index", async (page) => {
      await expect(page.getByRole("heading", { name: "Clients", exact: true })).toBeVisible();
      await expect(page.getByText(NORTHWIND).first()).toBeVisible();
    });
    await journey.step("CLI-02: Northwind's record", async (page) => {
      await page.getByRole("button", { name: `${NORTHWIND} actions` }).click();
      await page.getByRole("menuitem", { name: "Open" }).click();
      await expect(page.getByRole("heading", { name: /Northwind Robotics, Inc\./ })).toBeVisible();
      await expect(page.getByRole("region", { name: "Summary" })).toBeVisible();
    });
  });

  test("ENG-01 to ENG-02: Hannah Leclerc's engagements and the PY2025 EBP audit's gates", async ({
    journey,
  }) => {
    await journey.as("hannah-leclerc", "/engagements", { clock: DEMO_INSTANT });
    await journey.step("ENG-01: the Engagements index", async (page) => {
      await expect(page.getByRole("heading", { name: "Engagements" })).toBeVisible();
      await expect(page.getByText(/^Showing \d+ of \d+$/)).toBeVisible();
    });
    await journey.step("ENG-02b: G1 to G3 met, G4 blocked", async (page) => {
      await page
        .getByRole("row")
        .filter({ hasText: "Northwind" })
        .filter({ hasText: NORTHWIND_EBP })
        .first()
        .click();
      await expect(page.getByRole("heading", { name: /PY2025 EBP Audit/ })).toBeVisible();
      for (const gate of ["G1", "G2", "G3"]) {
        await expect(page.locator(`[data-gate='${gate}'][data-met='met']`)).toBeVisible();
      }
      await expect(page.locator("[data-gate='G4'][data-met='blocked']")).toBeVisible();
    });
  });
});
