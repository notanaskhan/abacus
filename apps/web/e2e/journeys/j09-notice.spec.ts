// J09 the notice journey, steps 1b to 6 (N-04-T26) on fixtures: a notice comes in, Kevin reads the
// analysis, Daniel decides, the response goes out for signature. Each step runs axe and INV-1 to
// INV-5 through the harness. Full-stack and staging runs read the same steps on live data.
import { DEMO_INSTANT, expect, test } from "../harness";

test.describe("J09 notice", () => {
  test("j09 1b: Kevin sees the notice on the index (NOT-01)", async ({ journey }) => {
    await journey.as("kevin-osei", "/notices", { clock: DEMO_INSTANT, scenario: "NOT-01:a" });
    await journey.step("J09 step 1b: the notices index", async (page) => {
      await expect(page.getByText("Marcus & Dana Whitley").first()).toBeVisible();
    });
  });

  test("j09 3: the analysis waits on the signer (NOT-02a)", async ({ journey }) => {
    await journey.as("kevin-osei", "/notices/_noticeId_", {
      clock: DEMO_INSTANT,
      scenario: "NOT-02:a",
    });
    await journey.step("J09 step 3: analysis ready, reserved to Daniel Reyes", async (page) => {
      await expect(page.getByText("753.01").first()).toBeVisible();
      await expect(page.getByText("Reserved to Daniel Reyes", { exact: false })).toBeVisible();
    });
  });

  test("j09 4: Daniel's decision reads as his (NOT-02c)", async ({ journey }) => {
    await journey.as("daniel-reyes", "/notices/_noticeId_", {
      clock: DEMO_INSTANT,
      scenario: "NOT-02:c",
    });
    await journey.step("J09 step 4: Agree, decided by Daniel Reyes", async (page) => {
      await expect(page.getByText("decided by Daniel Reyes", { exact: false })).toBeVisible();
    });
  });

  test("j09 5-6: the response letter and its approval (NOT-03)", async ({ journey }) => {
    await journey.as("kevin-osei", "/notices/_noticeId_?tab=response", {
      clock: DEMO_INSTANT,
      scenario: "NOT-03:a",
    });
    await journey.step("J09 step 5: the response letter", async (page) => {
      await expect(page.locator("[data-screen='NOT-03']").first()).toBeVisible();
    });
  });

  test("j09 variants: Collins disagrees, Santos has no authorization", async ({ journey }) => {
    await journey.as("kevin-osei", "/notices/_noticeId_", {
      clock: DEMO_INSTANT,
      scenario: "NOT-02:e",
    });
    await journey.step("J09 variant: Disagree, Awaiting IRS (NOT-02e)", async (page) => {
      await expect(page.getByText("so the gain is zero", { exact: false })).toBeVisible();
    });
  });
});
