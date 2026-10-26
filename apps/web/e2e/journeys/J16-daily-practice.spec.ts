// J16 daily practice (P-06-T25; blueprint §7.16): the firm admin's morning chase. Grace Holloway
// filters Binders to clients silent for 30 days and sends the Request Chaser's drafted follow-up;
// the agent drafts, a person sends (DEC-74). Each step runs axe and INV-1 to INV-5. In the fixture
// project the step walks BND-01's own scenario laid over the seed (`?scenario=`); the other
// projects wait for `binders.engine` on in E0 and the BND-01 live swap (P-06-T16).
import { expect, test } from "../harness";

const LIVE = "binders.engine is off in E0; the BND-01 live swap is P-06-T16's";

test.describe("J16", () => {
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
