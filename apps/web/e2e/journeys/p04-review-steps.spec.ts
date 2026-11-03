// The review grammar's journey steps (P-04-T57; P-04 §5; SHL-10, SHL-11, SHL-12, SHL-16): j03's
// materiality decision and Trial Balance L2 on Northwind, j23's partner bulk sign-off, j13's
// approve, and j06's coordination over a return's checkpoints, each walked on its host sheet's
// artboard (`/components/screens/SHL-1x?st=`) with axe and INV-1 to INV-5 after every step (the
// harness). Nothing here decides or signs: each step opens the sheet and reads what the person
// would act on (INV-1). Steps whose host screens are not live are `test.fixme` naming their epic.
//
// Fixture-first; full stack and staging walk the hosts' own routes once those are live (AUD-07,
// AUD-06 and the tax return pages) and the demo firm has the review flags (STAGING_JOURNEYS off).
import { expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const LIVE =
  "review.grammar_api is off in E0; full stack and staging walk the host routes once the demo firm has the review flags (P-04 flag plan, STAGING_JOURNEYS)";
const sheet = (screen: string, state: string): string =>
  `/components/screens/${screen}?st=${state}&frame=1`;

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("P-04 review grammar journey steps", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
  });

  test(
    "j03 7: Margaret opens the materiality decision; the options are one radio group (SHL-11 a)",
    owner("P-04 · P-04-T57 fixture; AUD-07 host full stack after A-04 · S25"),
    async ({ journey }) => {
      test.fixme(journey.project !== "fixture", LIVE);
      await journey.as("margaret-okonkwo", sheet("SHL-11", "a"));
      await journey.step("j03 7: the decision sheet, nothing decided", async (page) => {
        await expect(page.getByRole("dialog")).toBeVisible();
        await expect(page.getByRole("group", { name: "Qualitative factors" })).toBeVisible();
        await expect(page.getByRole("radio", { name: "1.5% — $252,200" })).toBeVisible();
      });
    },
  );

  test(
    "j03 8: Hannah opens the Trial Balance sign-off at L2 (SHL-12 a)",
    owner("P-04 · P-04-T57 fixture; AUD-06 host full stack after A-02 · S25"),
    async ({ journey }) => {
      test.fixme(journey.project !== "fixture", LIVE);
      await journey.as("hannah-leclerc", sheet("SHL-12", "a"));
      await journey.step("j03 8: the L2 sheet on the trial balance", async (page) => {
        await expect(page.getByRole("dialog")).toBeVisible();
        await expect(page.getByText("AUD-06").first()).toBeVisible();
      });
    },
  );

  test.fixme(
    "j23 2: Granite Peak's group materiality decision on AUD-07",
    owner("A-09 · Granite Peak group audit materiality (AUD-07 on the group seed) · S27"),
    async ({ journey }) => {
      await journey.as("margaret-okonkwo", "/audits");
    },
  );

  test(
    "j23 4: the partner's bulk sheet signs or excludes each item with words (SHL-12 f)",
    owner(
      "P-04 · P-04-T57 fixture at L2; the L4 partner pass waits for A-09's Granite Peak seed · S25",
    ),
    async ({ journey }) => {
      test.fixme(journey.project !== "fixture", LIVE);
      await journey.as("margaret-okonkwo", sheet("SHL-12", "f"));
      await journey.step("j23 4: six workpapers in one bulk sheet", async (page) => {
        await expect(page.getByRole("dialog")).toBeVisible();
        await expect(page.getByRole("button", { name: /^Sign off \d+ as /u })).toBeVisible();
      });
    },
  );

  test(
    "j13 3: the partner opens the approve sheet; nothing agent-owned approves (SHL-10 a)",
    owner("P-04 · P-04-T57 fixture; the tax host after T-04 · S25"),
    async ({ journey }) => {
      test.fixme(journey.project !== "fixture", LIVE);
      await journey.as("margaret-okonkwo", sheet("SHL-10", "a"));
      await journey.step("j13 3: Ready for review, the net change by code", async (page) => {
        await expect(page.getByText("Ready for review").first()).toBeVisible();
        await expect(page.getByText("Net change to Form 1040 total income")).toBeVisible();
      });
    },
  );

  test.fixme(
    "j13 4: the partner signs the return at L4 and the 8879 goes out",
    owner("T-04 · tax return sign and e-file host · S26"),
    async ({ journey }) => {
      await journey.as("margaret-okonkwo", "/returns");
    },
  );

  test(
    "j06 5: the preparer and reviewer coordinate over the return's checkpoints (SHL-16 a)",
    owner("P-04 · P-04-T57 fixture; the 1040 host after T-01 · S25"),
    async ({ journey }) => {
      test.fixme(journey.project !== "fixture", LIVE);
      await journey.as("hannah-leclerc", sheet("SHL-16", "a"));
      await journey.step("j06 5: the checkpoint drawer and its field diff", async (page) => {
        await expect(page.getByText("Proposed").first()).toBeVisible();
        await expect(page.getByRole("table", { name: "Field diff" })).toBeVisible();
      });
    },
  );
});
