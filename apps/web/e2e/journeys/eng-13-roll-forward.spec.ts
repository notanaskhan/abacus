// ENG-13 roll-forward walked in the app (P-07-T62; P-07 §10 DoD 1, `eng-13-roll-forward.spec.ts`):
// Hannah Leclerc rolls Northwind's archived PY2025 EBP audit into PY2026 (d, the live shape: 24
// requests carried as Draft, no evidence, the team asked for independence at Create), and Laura
// Kemp creates Tessellate's SOC 2 Type 2 from Review (e). Create is a person's click (INV-1) and
// the toast names the new engagement and its period. Every step runs axe and INV-1 to INV-5.
//
// The fixture project opens the real route (`/engagements/$engagementId/roll-forward`, which
// starts the source's draft) on ENG-13's own scenarios (`?screen=`, DEC-457), with
// `engagements.roll_forward_v2` on. Full stack and staging walk d once the flag is on in the demo
// firm and the demo seed archives Northwind PY2025 (E0 leaves both off; STAGING_JOURNEYS is off).
// e's SOC 2 carry stays fixture-only until X-01.
import { expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const LIVE =
  "engagements.roll_forward_v2 is off in E0 and the demo seed does not archive Northwind PY2025; full stack and staging walk ENG-13 d once the demo firm has both (P-07 flag plan, STAGING_JOURNEYS)";
const ROLL_FORWARD = "/engagements/_engagementId_/roll-forward";
const FLAGS = ["engagements.roll_forward_v2"];

test.describe("ENG-13 roll forward", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
    test.fixme(journey.project !== "fixture", LIVE);
  });

  test("eng-13 d: Hannah rolls Northwind PY2025 into PY2026 with 24 requests as Draft", async ({
    journey,
  }) => {
    await journey.as("hannah-leclerc", ROLL_FORWARD, { scenario: "ENG-13:d", flags: FLAGS });
    await journey.step("ENG-13 d: What to carry, the archive read-only", async (page) => {
      await expect(
        page.getByRole("heading", {
          name: "What to carry into PY2026 EBP Audit · Jan 1, 2026 – Dec 31, 2026",
        }),
      ).toBeVisible();
      await expect(
        page.getByText("24, as Draft; the client sees nothing until you send"),
      ).toBeVisible();
      await expect(page.getByText("Source released · Archived")).toBeVisible();
      await expect(page).toHaveURL(/[?&]draft=/);
    });
    await journey.step(
      "ENG-13 d: Team, each carried person asked for independence",
      async (page) => {
        const next = page.getByRole("button", { name: "Next" });
        await next.click(); // Template version
        await next.click(); // Team
        await expect(page.getByText("Independence requested at Create").first()).toBeVisible();
      },
    );
    await journey.step("ENG-13 d: Review and Create, a person's click", async (page) => {
      await page.getByRole("button", { name: "Next" }).click(); // Review
      await page.getByRole("button", { name: "Create", exact: true }).click();
      await expect(
        page
          .getByText("Engagement created · PY2026 EBP Audit · Jan 1, 2026 – Dec 31, 2026")
          .first(),
      ).toBeVisible();
    });
  });

  test("eng-13 e: Laura creates Tessellate's SOC 2 Type 2 from Review (fixture until X-01)", async ({
    journey,
  }) => {
    await journey.as("laura-kemp", ROLL_FORWARD, { scenario: "ENG-13:e", flags: FLAGS });
    await journey.step("ENG-13 e: Create names the period", async (page) => {
      // The route opens a resumed draft on What to carry: walk to Review.
      const next = page.getByRole("button", { name: "Next" });
      for (let i = 0; i < 3; i += 1) await next.click();
      await page.getByRole("button", { name: "Create", exact: true }).click();
      await expect(
        page.getByText("Engagement created · SOC 2 Type 2 · Oct 1, 2026 – Sep 30, 2027").first(),
      ).toBeVisible();
    });
  });
});
