// P-09-T19 (P-09 §8; SPEC-648): the agent dock and run trace steps of five journeys, walked on the
// harness (axe and INV-1 to INV-5 after every step: a decision or sign-off row carrying
// actor_kind agent fails the step). Fixture project: SHL-13 on AUD-02's run artboards and WB-09's
// drawer over firm pages (fixtures/screen-scenarios.ts "SHL-13" and "WB-09"). Compose and staging
// read the seeded runs; a step that needs a route not served yet is fixme with its owner.
//
//   j03 6   the run projection and the dock's trace link on Northwind's cockpit (plan approval: P-10-T33)
//   j03 10  the failed Internal Control step, Retry and Open trace
//   j18 5   Thomas Whitcombe reads run #4127's trace read-only; Lena Park is not allowed
//   j11 a4  run #4118's trace: Timeline, Records read, Writes & approvals
//   j10 4   Copperleaf's Run 2 card and its trace (fixture until C-01)
import { DEMO_INSTANT, expect, test } from "../harness";

const COCKPIT = "/audits/_auditId_";

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("P-09 agent runs (P-09-T19)", () => {
  test("j03 6: the run projection by level and the dock's trace link", async ({ journey }) => {
    test.fixme(journey.project !== "fixture", "the seeded run #4127 walks on staging (P-10)");
    await journey.as("hannah-leclerc", COCKPIT, { scenario: "SHL-13:a", clock: DEMO_INSTANT });
    await journey.step("J03 step 6: run #4127 projected by level in the dock", async (page) => {
      const pane = page.locator("[data-run-pane]");
      await expect(pane).toBeVisible();
      for (const level of ["Foundation", "Planning", "Sampling", "Testing", "Completion"]) {
        await expect(pane.getByText(level, { exact: true }).first()).toBeVisible();
      }
    });
    await journey.step("J03 step 6: Open trace opens WB-09 on the run", async (page) => {
      await page.locator("[data-run-pane]").getByText("Open trace").first().click();
      await expect(page.getByRole("dialog").last()).toContainText(
        "Northwind Robotics 401(k) Plan — PY2025 planning run",
      );
    });
  });

  test.fixme(
    "j03 6: Hannah approves the proposed plan from the dock",
    owner("P-10-T33 · the plan routes (S35); the plan card renders, its approve route does not"),
    async ({ journey }) => {
      await journey.as("hannah-leclerc", COCKPIT, { scenario: "SHL-13:c", clock: DEMO_INSTANT });
    },
  );

  test("j03 10: the failed step quotes the error, offers Retry and Open trace", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", "the seeded failure is the fixture's run (P-10)");
    await journey.as("hannah-leclerc", COCKPIT, { scenario: "SHL-13:e", clock: DEMO_INSTANT });
    await journey.step("J03 step 10: the failed tool card", async (page) => {
      const failed = page.locator("[data-tool-card='failed']").first();
      await expect(failed).toBeVisible();
      await expect(failed).toContainText("BH-EBP-140 step 8");
      await expect(failed.getByRole("button", { name: "Retry" })).toBeVisible();
    });
    await journey.step("J03 step 10: Open trace from the failed step", async (page) => {
      await page.locator("[data-tool-card='failed']").first().getByText("Open trace").click();
      await expect(page.getByRole("dialog").last()).toBeVisible();
    });
  });

  test("j18 5: Thomas reads run #4127's trace read-only", async ({ journey }) => {
    test.fixme(journey.project !== "fixture", "AUD-29's live trace link is staging's (P-09-T13)");
    await journey.as("thomas-whitcombe", "/audits", { scenario: "WB-09:b", clock: DEMO_INSTANT });
    await journey.step(
      "J18 step 5: WB-09b from the Agent link, nothing to decide",
      async (page) => {
        const drawer = page.getByRole("dialog").last();
        await expect(drawer).toContainText("Northwind Robotics 401(k) Plan — PY2025 planning run");
        for (const verb of ["Approve", "Sign off", "Decide", "Release"]) {
          await expect(drawer.getByRole("button", { name: new RegExp(`^${verb}`) })).toHaveCount(
            0,
          );
        }
      },
    );
  });

  test("j18 5: Lena Park's trace link answers not allowed", async ({ journey }) => {
    test.fixme(journey.project !== "fixture", "Lena's 403 is the fixture's (agent_run.read)");
    await journey.as("lena-park", "/audits", { scenario: "WB-09:n", clock: DEMO_INSTANT });
    await journey.step("J18 step 5: not allowed, no run data shown", async (page) => {
      const drawer = page.getByRole("dialog").last();
      await expect(drawer).toContainText("You don't have access to this run.");
      await expect(drawer).not.toContainText("PY2025 planning run");
    });
  });

  test("j11 a4: run #4118's trace through its three views", async ({ journey }) => {
    test.fixme(journey.project !== "fixture", "run #4118 is the fixture's scheduled run (P-10)");
    await journey.as("hannah-leclerc", "/workbench", { scenario: "WB-09:a", clock: DEMO_INSTANT });
    await journey.step("J11 step a4: the Timeline of run #4118", async (page) => {
      const drawer = page.getByRole("dialog").last();
      await expect(drawer).toContainText("Season Progress Reporter v2");
      await expect(drawer.getByRole("tab", { name: /Timeline/ })).toHaveAttribute(
        "aria-selected",
        "true",
      );
    });
    for (const view of ["Records read", "Writes & approvals"]) {
      await journey.step(`J11 step a4: ${view}`, async (page) => {
        const tab = page
          .getByRole("dialog")
          .last()
          .getByRole("tab", { name: new RegExp(view) });
        await tab.click();
        await expect(tab).toHaveAttribute("aria-selected", "true");
      });
    }
  });

  test("j10 4: Copperleaf's Run 2 and its trace (fixture until C-01)", async ({ journey }) => {
    test.fixme(journey.project !== "fixture", "the close run is fixture-only until C-01");
    await journey.as("priya-raman", "/closes", { scenario: "WB-09:d", clock: DEMO_INSTANT });
    await journey.step("J10 step 4: the Run 2 trace", async (page) => {
      await expect(page.getByRole("dialog").last()).toContainText("Closing agent");
    });
  });
});
