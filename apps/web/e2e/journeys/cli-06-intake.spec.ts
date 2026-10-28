// CLI-06 intake and bulk import walked in the app (P-07-T62; P-07 §10 DoD 1, `cli-06-intake.spec.ts`):
// the validation that jumps back to the step that needs the answer (i), a manager clearing a
// counterparty hit as a person (h, INV-1), and Grace's season-start bulk import of the CCH Axcess
// Tax client list (g): the synthetic 212-row export P-07-T50 commits, uploaded through the file
// picker, its headings mapped, 204 matched + 8 to review + 0 new, rows 7 and 8 skipped, "Import
// 210 records", then "210 records imported · 2 skipped · 0 new clients". Every step runs axe and
// INV-1 to INV-5 (the harness); the single intake's whole walk is J19 step 0
// (J19-estate-amended.spec.ts).
//
// The fixture project walks the real route (`/clients/new`, `?mode=import`) on CLI-06's own
// scenarios (`?screen=`, DEC-457). Full stack and staging walk the same steps once `clients.v2` is
// on in the demo firm and the demo seed carries the Thornbury holdout (E0 leaves both off;
// STAGING_JOURNEYS is off until staging exists, F-04-T28): until then they are `test.fixme`.
import { expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const LIVE =
  "clients.v2 is off in E0 and the demo seed holds no Thornbury holdout; full stack and staging walk CLI-06 once the demo firm has both (P-07 flag plan, STAGING_JOURNEYS)";
// The synthetic CCH Axcess Tax client list (P-07-T50), from the app's folder (Playwright's cwd).
const CCH_EXPORT =
  "../../backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/files/cch-axcess-client-list.csv";

test.describe("CLI-06 intake and bulk import", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
    test.fixme(journey.project !== "fixture", LIVE);
  });

  test("cli-06 i: Next on Services sends Grace back to the date of death", async ({ journey }) => {
    await journey.as("grace-holloway", "/clients/new", { scenario: "CLI-06:i" });
    await journey.step("CLI-06 b: the estate's details, date of death empty", async (page) => {
      await expect(page.getByText("96% match · Walter Thornbury").first()).toBeVisible();
    });
    await journey.step("CLI-06 i: Services' Next says why and opens the field", async (page) => {
      const next = page.getByRole("button", { name: "Next" });
      await next.click();
      await expect(
        page.getByText("Disclosure to a fiduciary is permitted under §301.7216-2(j)."),
      ).toBeVisible();
      await next.click();
      await expect(page.getByRole("textbox", { name: "Name" })).toHaveValue("Paul Thornbury");
      await next.click();
      await expect(page.getByRole("checkbox", { name: "Form 706" })).toBeVisible();
      await next.click();
      await expect(page.getByText("Required for Form 706 due date").first()).toBeVisible();
      await expect(page.getByText("96% match · Walter Thornbury").first()).toBeVisible();
    });
  });

  test("cli-06 h: Samuel Ito clears Harborline as not adverse, a person's decision (INV-1)", async ({
    journey,
  }) => {
    await journey.as("samuel-ito", "/clients/new", { scenario: "CLI-06:h" });
    await journey.step("CLI-06 h: a counterparty hit to review", async (page) => {
      await expect(page.getByText("Harborline Trust Company").first()).toBeVisible();
      await expect(page.getByText("No conflicts")).toHaveCount(0);
    });
    await journey.step("CLI-06 h: cleared with a reason; no conflicts left", async (page) => {
      await page.getByRole("button", { name: "Clear as not adverse…" }).click();
      const dialog = page.getByRole("dialog");
      await dialog.getByRole("textbox").fill("Custodian only; no adverse interest.");
      await dialog.getByRole("button", { name: "Clear", exact: true }).click();
      await expect(page.getByText("No conflicts").first()).toBeVisible();
    });
  });

  test("cli-06 g: Grace imports the CCH client list: 210 imported, 2 skipped, 0 new", async ({
    journey,
  }) => {
    await journey.as("grace-holloway", "/clients/new?mode=import", { scenario: "CLI-06:g" });
    await journey.step("CLI-06 g: Source, the CCH export chosen", async (page) => {
      await expect(page.getByRole("tab", { name: "Bulk import" })).toHaveAttribute(
        "aria-selected",
        "true",
      );
      await page.locator("input[type='file']").setInputFiles(CCH_EXPORT);
      await expect(page.getByText("Chosen: cch-axcess-client-list.csv")).toBeVisible();
    });
    await journey.step(
      "CLI-06 g: Map fields, the headings as the export names them",
      async (page) => {
        await page.getByRole("button", { name: "Next" }).click();
        const map = page.getByRole("table", { name: "Map fields" });
        await expect(map.getByText("Client Name", { exact: true })).toBeVisible();
        await expect(map.getByText("Client name", { exact: true })).toBeVisible();
      },
    );
    await journey.step(
      "CLI-06 g: 204 matched, 8 to review, 0 new; rows 7 and 8 skipped",
      async (page) => {
        await page.getByRole("button", { name: "Next" }).click();
        const tallies = page.getByRole("list", { name: "Import tallies" });
        await expect(tallies.getByText("MATCHED AUTOMATICALLY")).toBeVisible();
        await expect(tallies.getByText("204")).toBeVisible();
        await expect(tallies.getByText("8", { exact: true })).toBeVisible();
        const rows = page.getByRole("table", { name: "Records to review" }).getByRole("row");
        await expect(rows).toHaveCount(9);
        const seven = page.getByRole("tablist", {
          name: "Decision for Harbourview Dental Properties LP",
        });
        await expect(seven.getByRole("tab", { name: "Skip" })).toHaveAttribute(
          "aria-selected",
          "true",
        );
        await expect(page.getByRole("button", { name: "Import 210 records" })).toBeEnabled();
      },
    );
    await journey.step("CLI-06 g: Import 210 records, then the counts", async (page) => {
      await page.getByRole("button", { name: "Import 210 records" }).click();
      await expect(
        page.getByText("210 records imported · 2 skipped · 0 new clients").first(),
      ).toBeVisible();
      await expect(page.getByRole("button", { name: "Done", exact: true })).toBeEnabled();
    });
  });
});
