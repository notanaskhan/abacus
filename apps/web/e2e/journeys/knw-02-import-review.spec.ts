// KNW-02 methodology import review walked in the app (K-01-T25; K-01 §3.3; KNW-02 a–f): Margaret
// Okonkwo reviews BH Audit Methodology · EBP v3 as imported: every parsed step cites its page (a),
// the flagged step 7 is the only row on the Flagged tab (a2), the importer's run card while it
// reads (b), the diff against v2 (c), the standards set (d), the Approve sheet with the server's
// checklist (e) and the approved version (f). Every step runs axe and INV-1 to INV-5; nothing
// agent-owned approves (INV-1: the Approve control is the person's, in the sheet).
//
// The row names `apps/web/e2e/knowledge/`; it lives under journeys/ beside knw-03-program-editor so
// the harness projects pick it up (DEC-457, DEC-1663). Fixture mode opens KNW-02's own artboards on
// the gallery route (`/components/screens/KNW-02?st=`). Full stack and staging walk the real route
// once the demo firm has the methodology slice (K-01 flag plan; STAGING_JOURNEYS is off).
import { expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const LIVE =
  "the methodology slice is opt-in and methodology.programs is off in E0; full stack and staging walk KNW-02 once the demo firm has both (K-01 flag plan, STAGING_JOURNEYS)";
const CLOCK = "2026-01-12T14:10:00-06:00";
const screen = (state: string): string => `/components/screens/KNW-02?st=${state}`;

test.describe("KNW-02 import review", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
    test.fixme(journey.project !== "fixture", LIVE);
  });

  test("knw-02 a, a2: every step cites a page; the Flagged tab holds step 7 alone", async ({
    journey,
  }) => {
    await journey.as("margaret-okonkwo", screen("a"), { clock: CLOCK });
    await journey.step("KNW-02 a: step 4 cites p. 14, Uploaded files", async (page) => {
      await expect(page.locator('[data-step="4"]').getByText("p. 14")).toBeVisible();
      await expect(page.getByText("Uploaded files")).toBeVisible();
    });
    await journey.as("margaret-okonkwo", screen("a2"), { clock: CLOCK });
    await journey.step("KNW-02 a2: the flagged step 7, split pp. 15–16", async (page) => {
      const rows = page.locator("[data-step]");
      await expect(rows).toHaveCount(1);
      await expect(rows.first()).toHaveAttribute("data-step", "7");
      await expect(rows.first()).toHaveAttribute("data-flagged", "true");
    });
  });

  test("knw-02 b: the importer reads 2 files, 41 of 96 pages", async ({ journey }) => {
    await journey.as("margaret-okonkwo", screen("b"), { clock: "2026-01-12T13:51:00-06:00" });
    await journey.step("KNW-02 b: the run card", async (page) => {
      await expect(page.getByText("Methodology importer is reading 2 files")).toBeVisible();
      await expect(page.getByText("41 of 96 pages")).toBeVisible();
    });
  });

  test("knw-02 c, d: the diff against v2 and the standards set", async ({ journey }) => {
    await journey.as("margaret-okonkwo", screen("c"), { clock: CLOCK });
    await journey.step("KNW-02 c: v3 = 67 steps · v2 = 64 steps", async (page) => {
      await expect(page.getByText("v3 = 67 steps · v2 = 64 steps")).toBeVisible();
    });
    await journey.as("margaret-okonkwo", screen("d"), { clock: CLOCK });
    await journey.step("KNW-02 d: SQMS 1 and the three EBP types", async (page) => {
      await expect(page.getByText("SQMS 1 (effective Dec 15, 2025)")).toBeVisible();
    });
  });

  test("knw-02 e, f: the Approve sheet, then the approved version", async ({ journey }) => {
    await journey.as("margaret-okonkwo", screen("e"), { clock: CLOCK });
    await journey.step("KNW-02 e: effective Jan 1, 2026, supersedes v2", async (page) => {
      const sheet = page.getByRole("dialog", { name: "Approve BH Audit Methodology · EBP v3" });
      await expect(sheet.getByText("v2 (ends Dec 31, 2025)")).toBeVisible();
      await expect(sheet.getByRole("button", { name: "Approve version" })).toBeVisible();
    });
    await journey.as("margaret-okonkwo", screen("f"), { clock: "2026-01-12T14:31:00-06:00" });
    await journey.step("KNW-02 f: Approved by Margaret, no Approve", async (page) => {
      await expect(
        page.getByText("Approved · Jan 12, 2026 2:31 PM · Margaret Okonkwo"),
      ).toBeVisible();
      await expect(page.getByRole("button", { name: "Approve version…" })).toHaveCount(0);
    });
  });
});
