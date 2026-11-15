// Workbench sessions on staging (W-02-T26; W-02 §10 item 1; WB-01, WB-02, WB-03). Real auth, fakes
// only for third parties and the model; every step asserts INV-1 to INV-5 and axe through the
// journey harness. The staging and fullstack projects run it (P-10-T50); the fixture project
// keeps it fixme, because walls, streams and partial failures need the live runtime.
import { expect, test } from "../harness";

test.describe("sessions (staging)", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(
      journey.project === "fixture",
      "walls, SSE streams and partial failures need the live runtime: staging and fullstack (P-10-T50)",
    );
  });

  test('sessions 1: filters, search "K-3" with no results, rename and delete keep the run trace', async ({
    journey,
  }) => {
    await journey.as("hannah-leclerc", "/workbench");
    await journey.step("sessions 1: search with no results", async (page) => {
      await page.getByRole("searchbox", { name: /Search sessions/ }).fill("K-3");
      await expect(page.getByText(/No sessions match/)).toBeVisible();
    });
  });

  test("sessions 2: Hannah opens the Copperleaf session and sees the locked thread with no figures", async ({
    journey,
  }) => {
    await journey.as("hannah-leclerc", "/workbench");
    await journey.step("sessions 2: the locked Copperleaf thread", async (page) => {
      await page.getByRole("link", { name: /Copperleaf/ }).click();
      await expect(page.getByText(/locked/i)).toBeVisible();
      await expect(page.locator("[data-figure]")).toHaveCount(0);
    });
  });

  test('sessions 3: Margaret Okonkwo follows the HOME-01 "3 running" pill to Running 3, then Running 4 at 9:25', async ({
    journey,
  }) => {
    await journey.as("margaret-okonkwo", "/");
    await journey.step("sessions 3: Running 3 from Home", async (page) => {
      await page.getByRole("link", { name: /3 running/ }).click();
      await expect(page.getByText("Running 3")).toBeVisible();
    });
  });

  test("sessions 4: a wall on Northwind for Ana Cruz removes the session from her list, counts and search and closes its stream", async ({
    journey,
  }) => {
    await journey.as("ana-cruz", "/workbench");
    await journey.step("sessions 4: the walled session is gone", async (page) => {
      await expect(page.getByText(/Northwind/)).toHaveCount(0);
    });
  });

  test('sessions 5: a partial failure retries only the 3 unreadable binders and the card reads "Prepared with 1 gap"', async ({
    journey,
  }) => {
    await journey.as("hannah-leclerc", "/workbench");
    await journey.step("sessions 5: the partial retry", async (page) => {
      await page.getByRole("button", { name: /Retry 3/ }).click();
      await expect(page.getByText("Prepared with 1 gap")).toBeVisible();
    });
  });

  test('sessions 6: on a non-synthetic tenant the composer reads "AI isn\'t available for real client data yet"', async ({
    journey,
  }) => {
    await journey.as("hannah-leclerc", "/workbench", { scenario: "WB-01:real-firm" });
    await journey.step("sessions 6: the DF-04 composer", async (page) => {
      await expect(page.getByText("AI isn't available for real client data yet")).toBeVisible();
    });
  });

  test('sessions 7: at 2:40 PM Hannah attaches the Northwind client record, PBC 12 of 24 and the planning workpapers and gets a cited $48,600 answer that ends "Nothing was written."; the picker never lists Copperleaf', async ({
    journey,
  }) => {
    await journey.as("hannah-leclerc", "/workbench/sessions/new");
    await journey.step("sessions 7: a grounded, cited answer", async (page) => {
      await page.getByRole("button", { name: /Add context/ }).click();
      await expect(page.getByRole("menuitemcheckbox", { name: /Copperleaf/ })).toHaveCount(0);
      await expect(page.getByText(/\$48,600/)).toBeVisible();
      await expect(page.getByText("Nothing was written.")).toBeVisible();
    });
  });
});
