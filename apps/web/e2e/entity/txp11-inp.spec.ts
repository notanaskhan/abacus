// INP on TXP-11 with 2,000 cells (T-05-T69; T-05 §5.5, §10 item 4): "INP ≤ 200 ms on TXP-11 with
// 2,000 cells in the nightly trace". The `load` state serves sheet 01's cells repeated to 2,000
// (screen-scenarios.ts); the trace selects cells by click and walks the grid by keyboard, then
// reads Chromium's Event Timing entries and takes the slowest interaction (INP for fewer than 50
// interactions). Fixture project on pull requests; the nightly trace runs the same spec.
import { expect, test } from "../harness";

const FLAGS = ["tax.entity_workspace", "tax.review_workspace"];
const BUDGET_MS = 200;

test.describe("TXP-11 INP (T-05-T69)", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", "T-05-T69: the nightly full-stack trace");
  });

  test("TXP-11 with 2,000 cells: INP is at or under 200 ms", async ({ journey }) => {
    await journey.as("olivia-brandt", "/tax-returns/_returnId_/workpaper", {
      scenario: "TXP-11:load",
      flags: FLAGS,
    });
    await journey.step("TXP-11 load: 2,000 cells, interactions within budget", async (page) => {
      const grid = page.getByRole("grid").first();
      await expect(grid).toBeVisible();
      await page.evaluate(() => {
        const w = window as unknown as { __inp: number[] };
        w.__inp = [];
        new PerformanceObserver((list) => {
          for (const e of list.getEntries() as (PerformanceEntry & { interactionId?: number })[]) {
            if ((e.interactionId ?? 0) > 0) w.__inp.push(e.duration);
          }
        }).observe({
          type: "event",
          durationThreshold: 16,
          buffered: true,
        } as PerformanceObserverInit);
      });
      const cells = grid.getByRole("gridcell");
      expect(await cells.count()).toBeGreaterThan(100);
      for (const i of [5, 40, 90]) await cells.nth(i).click();
      await grid.focus();
      for (let i = 0; i < 30; i += 1)
        await page.keyboard.press(i % 3 === 0 ? "ArrowRight" : "ArrowDown");
      await page.keyboard.press("PageDown");
      await page.waitForTimeout(500);
      const durations = await page.evaluate(
        () => (window as unknown as { __inp: number[] }).__inp,
      );
      const inp = durations.length === 0 ? 0 : Math.max(...durations);
      test.info().annotations.push({
        type: "INP",
        description: `${String(inp)} ms over ${String(durations.length)} entries`,
      });
      expect(inp, "INP (ms)").toBeLessThanOrEqual(BUDGET_MS);
    });
  });
});
