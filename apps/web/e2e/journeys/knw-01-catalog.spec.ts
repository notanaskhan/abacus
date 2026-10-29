// KNW-01 catalog walked in the app (K-01-T11; K-01 §10 DoD 1, `knw-01-catalog.spec.ts`): Margaret
// Okonkwo's library (a, b), review queue (c) and change log (d), Ana Cruz's staff view (e) and the
// "materiality" search (f). Every step runs axe and INV-1 to INV-5. No control on the screen
// publishes or approves (INV-1); the change log never names the agent as an approver (INV-5); the
// staff view's drafts are left out by the API, not hidden by the UI (AC1.6).
//
// Lives under journeys/ so the harness (persona adapters, axe, invariants) runs it in the fixture
// project on KNW-01's own scenarios (`?screen=KNW-01&st=`, DEC-457), with `knowledge.catalog` on
// (DEC-902). Full stack and staging walk it once the demo firm has the flag and the methodology
// slice in E0 (K-01-T10's `--slice methodology` is opt-in; STAGING_JOURNEYS is off).
import { expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const LIVE =
  "knowledge.catalog is off in E0 and the methodology slice is opt-in; full stack and staging walk KNW-01 once the demo firm has both (K-01 flag plan, STAGING_JOURNEYS)";
const FLAGS = ["knowledge.catalog"];
const CARD = "[data-catalog-card]";

test.describe("KNW-01 knowledge catalog", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
    test.fixme(journey.project !== "fixture", LIVE);
  });

  test("knw-01 a, b: Margaret's library foots 48 and Methodology keeps the superseded EBP", async ({
    journey,
  }) => {
    await journey.as("margaret-okonkwo", "/knowledge", { scenario: "KNW-01:a", flags: FLAGS });
    await journey.step("KNW-01 a: All 48, the + menu, two waiting for review", async (page) => {
      await expect(page.locator(CARD)).toHaveCount(48);
      await expect(page.getByRole("button", { name: "Add to knowledge" })).toBeVisible();
      await expect(page.getByRole("tab", { name: /Review queue/u })).toContainText("2");
      await expect(page.getByText("Used by 14 engagements").first()).toBeVisible();
      await expect(page.getByRole("button", { name: /^(Publish|Approve)/u })).toHaveCount(0);
    });
    await journey.as("margaret-okonkwo", "/knowledge", { scenario: "KNW-01:b", flags: FLAGS });
    await journey.step("KNW-01 b: Methodology 4, card 4 Superseded", async (page) => {
      await page.getByRole("option", { name: /^Methodology\b/u }).click();
      await expect(page.locator(CARD)).toHaveCount(4);
      await expect(page.locator(CARD).nth(3)).toHaveAttribute(
        "aria-label",
        "BH Audit Methodology · EBP, Superseded",
      );
      await expect(page.getByText("Kept for engagements archived under it.")).toBeVisible();
    });
  });

  test("knw-01 c, d: the review queue and a change log that names the person", async ({
    journey,
  }) => {
    await journey.as("margaret-okonkwo", "/knowledge", { scenario: "KNW-01:c", flags: FLAGS });
    await journey.step("KNW-01 c: 1040 Review Checklist v7 and the §754 memo", async (page) => {
      // The route carries no tab in its URL: the walk opens the tab as a person does.
      await page.getByRole("tab", { name: /Review queue/u }).click();
      const rows = page.locator("[data-review-row]");
      await expect(rows).toHaveCount(2);
      await expect(rows.first()).toContainText("1040 Review Checklist v7 (TY2026)");
      await expect(rows.nth(1)).toContainText("§754 election — Ridgeline");
    });
    await journey.as("margaret-okonkwo", "/knowledge", { scenario: "KNW-01:d", flags: FLAGS });
    await journey.step("KNW-01 d: newest last, never the agent as approver", async (page) => {
      await page.getByRole("tab", { name: /Change log/u }).click();
      const lines = page.locator("[data-change]");
      await expect(lines).toHaveCount(4);
      await expect(lines.first()).toContainText(
        "BH Audit Methodology · EBP v3 approved by Margaret Okonkwo · effective Jan 1, 2026",
      );
      await expect(page.locator("body")).not.toContainText("approved by Accrued Agent");
    });
  });

  test("knw-01 e: Ana Cruz sees no + menu and no drafts", async ({ journey }) => {
    await journey.as("ana-cruz", "/knowledge", { scenario: "KNW-01:e", flags: FLAGS });
    await journey.step("KNW-01 e: staff view, 47 cards, none Draft", async (page) => {
      await expect(page.locator(CARD)).toHaveCount(47);
      await expect(page.getByRole("button", { name: "Add to knowledge" })).toHaveCount(0);
      await expect(page.locator(`${CARD}[aria-label$=", Draft"]`)).toHaveCount(0);
    });
  });

  test("knw-01 f: materiality finds cards 8 and 1 with one plain search mark", async ({
    journey,
  }) => {
    await journey.as("margaret-okonkwo", "/knowledge", { scenario: "KNW-01:f", flags: FLAGS });
    await journey.step("KNW-01 f: Materiality ranges, then the EBP methodology", async (page) => {
      await page.getByLabel("Search knowledge", { exact: true }).fill("materiality");
      await expect(page.locator(CARD)).toHaveCount(2);
      await expect(page.locator(`${CARD} p[title]`).first()).toHaveAttribute(
        "title",
        "Materiality ranges",
      );
      const marks = page.locator("[data-search-hit]");
      await expect(marks).toHaveCount(1);
      await expect(marks.first()).toHaveText("Materiality");
      await expect(marks.first()).not.toHaveClass(/match-/u);
    });
  });
});
