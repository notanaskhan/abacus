// T-07-T31 (TASK-8361): axe and INV-1 to INV-5 on every TXT artboard in the fixture project.
// Each `journey.step` runs axe (serious and critical = 0; forced colours on the first step) and
// the invariants on the page as it stands. TXT-01 a–d (with d1–d3), TXT-02 a–e and f1, TXT-03 and
// TXT-04 a–e. Tier C parity is unmeasured: the local baselines (2026-10-21) hold no TXT crops.
import { expect, test } from "../harness";

const BOARDS: Record<string, readonly string[]> = {
  "TXT-01": ["a", "a2", "a3", "a4", "b", "c", "d", "d1", "d2", "d3"],
  "TXT-02": ["a", "a2", "b", "c", "d", "e", "f1", "error"],
  "TXT-03": ["a", "b", "c", "d", "e"],
  "TXT-04": ["a", "b", "c", "d", "e"],
};

test.describe("T-07 TXT artboards", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", "T-07-T31: the fixture project only");
  });

  for (const [screen, states] of Object.entries(BOARDS)) {
    test(`${screen}: every artboard passes axe and the invariants`, async ({ journey }) => {
      for (const st of states) {
        await journey.as("samuel-ito", `/components/screens/${screen}?st=${st}`);
        await journey.step(`${screen} ${st}`, async (page) => {
          await expect(page.getByText("Not built")).toHaveCount(0);
          await expect(
            page.locator(`[data-artboard="${st}"], [data-scenario="${st}"]`).first(),
          ).toBeVisible();
        });
      }
    });
  }
});
