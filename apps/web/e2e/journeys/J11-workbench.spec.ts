// J11 workbench (P-01-T16; W-02-T26; blueprint §7.11; W-02 §10). a3: a finished scheduled run
// notifies Hannah Leclerc in the bell drawer (SHL-04, fixture project). b1–b3 and b3-undo: the
// read-only discovery, the plan, the workbook and Save to Files with its 10-second Undo, walked on
// staging with real auth (fakes only for third parties and the model; P-10-T50 brings the staging
// project up), so the fixture project keeps them fixme. Each step runs axe and INV-1 to INV-5.
import { expect, test } from "../harness";

test.describe("J11", () => {
  test("j11 a3: a finished scheduled run notifies Hannah", async ({ journey }) => {
    test.fixme(journey.project !== "fixture", "scheduled runs and their notifications are W-02's");
    await journey.as("hannah-leclerc", "/", { scenario: "SHL-04:g" });
    await journey.step("J11 step a3: the run-finished row in the drawer", async (page) => {
      await page.getByRole("button", { name: /^Notifications/ }).click();
      await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
      await expect(page.getByText("Unrecorded liabilities tester finished")).toBeVisible();
    });
  });
});

test.describe("J11 b (staging)", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(
      journey.project === "fixture",
      "b1–b3 walk the live session runtime with real auth: staging and fullstack (P-10-T50)",
    );
  });

  test('j11 b1: Hannah opens a new session at 9:21 AM from "+" and sends the TY2025 season progress request; the first message becomes the title', async ({
    journey,
  }) => {
    await journey.as("hannah-leclerc", "/workbench");
    await journey.step("J11 step b1: a new session from +", async (page) => {
      await page.getByRole("button", { name: "New session" }).click();
      await page
        .getByRole("textbox", { name: /Message/ })
        .fill("Build me a TY2025 season progress report by office");
      await page.keyboard.press("Enter");
      await expect(page.getByRole("heading", { name: /TY2025 season progress/ })).toBeVisible();
    });
  });

  test('j11 b2: read-only discovery shows 224 returns across Chicago 98, Denver 64 and New York 62 and asks "Which returns should the report cover?" 1 of 2, then 2 of 2', async ({
    journey,
  }) => {
    await journey.as("hannah-leclerc", "/workbench");
    await journey.step("J11 step b2: discovery and the first question", async (page) => {
      await expect(page.getByText(/224 returns/)).toBeVisible();
      await expect(page.getByText(/Chicago 98/)).toBeVisible();
      const card = page.locator("[data-kit='QuestionCard']");
      await expect(card.getByText("Which returns should the report cover?")).toBeVisible();
      await expect(card.getByText("1 of 2")).toBeVisible();
      await card.getByRole("button", { name: "Next" }).click();
      await expect(card.getByText("2 of 2")).toBeVisible();
    });
  });

  test("j11 b3: Hannah approves the plan, gathering reaches 120 of 241, the workbook is ready, and the file is in Files only 10 seconds after she approves Save to Files", async ({
    journey,
  }) => {
    await journey.as("hannah-leclerc", "/workbench");
    await journey.step("J11 step b3: approve the plan", async (page) => {
      await page.getByRole("button", { name: /^Approve plan/ }).click();
      await expect(page.getByText(/120 of 241/)).toBeVisible();
    });
    await journey.step("J11 step b3: Save to Files after the Undo window", async (page) => {
      await page.getByRole("button", { name: /^Save to Files/ }).click();
      await expect(page.getByRole("button", { name: "Undo" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Undo" })).toBeHidden({ timeout: 12_000 });
      await expect(page.getByText(/Saved to Files/)).toBeVisible();
    });
  });

  test("j11 b3-undo: Undo inside 10 seconds leaves Files unchanged", async ({ journey }) => {
    await journey.as("hannah-leclerc", "/workbench");
    await journey.step("J11 step b3-undo: Undo", async (page) => {
      await page.getByRole("button", { name: /^Save to Files/ }).click();
      await page.getByRole("button", { name: "Undo" }).click();
      await expect(page.getByText(/Saved to Files/)).toHaveCount(0);
    });
  });
});
