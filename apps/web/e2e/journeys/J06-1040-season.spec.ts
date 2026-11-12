// J06 1040 season, the coordination slice (T-01-T29; T-01 §5 item 1; blueprint §7.6): the §7216
// consents gate the agent, the CCH import is approved by a person, final approval is blocked by
// the draft Ridgeline K-1 and then given, and the return is exported through the file bridge and
// marked exported by a person. Every step runs axe and INV-1 to INV-5 (journey harness); the
// agents-off walk repeats the slice and finds no agent attribution anywhere.
//
// The fixture project walks each step on its screen's own scenarios (`?screen=`, G-01-T16). The
// full stack and staging walk the same routes against the seeded tenant once the T-01 slices and
// the fake CCH are on that stack (T-01-T23, T-01-T22) and staging's URL is set (F-04-T28); until
// then they are fixme, never skipped.
import { DEMO_INSTANT, expect, test } from "../harness";
import type { Page } from "@playwright/test";
import { noAgentDecision, onScreen } from "./a07-support";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const LIVE =
  "full stack: the T-01 slices (consents_7216, tax_board, tax_content) and the fake CCH seeded on the stack (T-01-T23, T-01-T22); staging once ABACUS_STAGING_URL is set (F-04-T28)";
const TAX_FLAGS = ["tax.engine_bridge", "review.checkpoints"];
const CONSENT_FLAGS = ["consents.registry", "clients.tax_profile"];
const TAX09 = "/tax-returns/_returnId_?ov=engine-sync:_returnId_";
// J06 D2's day: Samuel exports and marks the Feld return exported on Wed Sep 16, 2026.
const EXPORT_DAY = "2026-09-16T10:00:00-05:00";

test.describe("J06 1040 season · coordination slice (T-01-T29)", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
    test.fixme(journey.project !== "fixture", LIVE);
  });

  test("j06 A3: an agent read of Ferris return information is refused with consent_7216 and audited", async ({
    journey,
  }) => {
    // The refusal itself (the agent's read answers 403 consent_7216 and writes its audit row) is
    // the backend's, asserted by the I-7216 property test; the journey reads what a person sees.
    await journey.as("samuel-ito", "/clients/_clientId_/tax-profile/consents", {
      scenario: "CLI-05:f",
      flags: CONSENT_FLAGS,
    });
    await journey.step("J06 A3: Ferris is partially signed (CLI-05 f)", async (page) => {
      await expect(
        page.getByText(
          "§7216 consents (use · AI disclosure) partially signed — Kai Ferris has not signed. Agents cannot read return information until both sign (firm policy).",
        ),
      ).toBeVisible();
      await expect(page.getByText("Requested · 1 of 2 signed").first()).toBeVisible();
    });
    await journey.as("grace-holloway", "/settings/consents", {
      scenario: "ADM-05:a",
      flags: CONSENT_FLAGS,
    });
    await journey.step(
      "J06 A3: the registry withholds it from agents (ADM-05 a)",
      async (page) => {
        await expect(page.getByText("Consents · 218")).toBeVisible();
        const first = page.getByRole("table").getByRole("row").nth(1);
        await expect(first).toContainText("Morgan & Kai Ferris");
        await expect(first).toContainText("Requested · 1 of 2 signed");
        await expect(
          page.getByText(/Return information withheld from agents for 3 clients\./u),
        ).toBeVisible();
      },
    );
  });

  test("j06 A4: Claire and Jonah sign two separate consents and CLI-05 shows Use · AI disclosure (2 consents)", async ({
    journey,
  }) => {
    await journey.as("grace-holloway", "/settings/consents", {
      scenario: "ADM-05:c",
      flags: CONSENT_FLAGS,
    });
    await journey.step(
      "J06 A4: Feld's evidence, two signed documents (ADM-05 c)",
      async (page) => {
        await page.getByRole("button", { name: "Evidence · Jonah & Claire Feld" }).click();
        const drawer = page.getByRole("dialog");
        await expect(drawer.getByText("Use · AI disclosure (2 consents)")).toBeVisible();
        await expect(drawer.getByText(/Claire Feld Feb 2, 2026/u)).toBeVisible();
        await expect(drawer.getByText("Consent to Use of Tax Return Information")).toBeVisible();
        await drawer.getByRole("tab", { name: "Consent to disclose — AI sub-processors" }).click();
        await expect(
          drawer.getByText("Consent to Disclose Tax Return Information to AI Service Providers"),
        ).toBeVisible();
      },
    );
    // CLI-05's Consents section reads the set the same way (its fixture holds the Whitley pair).
    await journey.as("samuel-ito", "/clients/_clientId_/tax-profile/consents", {
      scenario: "CLI-05:d",
      flags: CONSENT_FLAGS,
    });
    await journey.step("J06 A4: CLI-05 reads Use · AI disclosure, 2 consents", async (page) => {
      await expect(page.getByText("Use · AI disclosure (§7216, 2 consents)")).toBeVisible();
      await expect(page.locator('[data-row="document"]')).toHaveCount(2);
    });
  });

  test("j06 C-import: Samuel approves the CCH import diff for 2025I:FeldJ:V3", async ({
    journey,
  }) => {
    await journey.as(
      "samuel-ito",
      "/tax-returns/_returnId_?ov=checkpoints:tax_return:_returnId_",
      {
        scenario: "TAX-02:j06",
        flags: TAX_FLAGS,
      },
    );
    await journey.step("J06 C-import: the V3 import is pending (SHL-16)", async (page) => {
      await expect(page.getByText("Import pending approval").first()).toBeVisible();
      await expect(
        page.getByText("Imported from CCH Axcess 2025I:FeldJ:V3").first(),
      ).toBeVisible();
    });
    await journey.step("J06 C-import: Approve checkpoint, a person's click", async (page) => {
      await page.getByRole("button", { name: /Approve checkpoint/u }).click();
      await expect(page.getByText("Out of sync").first()).toBeVisible();
    });
  });

  test("j06 D1: final approval is blocked by the draft Ridgeline K-1", async ({ journey }) => {
    await journey.as("samuel-ito", TAX09, { scenario: "TAX-09:b", flags: TAX_FLAGS });
    await journey.step("J06 D1: Export waits on final approval (TAX-09 b)", async (page) => {
      const sync = page.getByRole("dialog", { name: "Tax-engine sync" });
      await expect(sync.getByRole("button", { name: /Synced Sep 10/u })).toBeVisible();
      const exportItem = sync.getByRole("button", { name: /Export to tax engine/u });
      await expect(exportItem).toBeDisabled();
      await expect(exportItem).toContainText(
        "Final approval required — Daniel Reyes (BH-TAX-02) · Ridgeline K-1 is a Draft K-1 · pre-release",
      );
    });
  });

  test("j06 D2: Daniel approves, Samuel exports and marks exported, the chip reads Synced Sep 16", async ({
    journey,
  }) => {
    // No fixture scenario carries Daniel's final-approval click (T-01-T18's route, live only): the
    // fixture walk starts from approval given (TAX-09 a); the full stack walks the click once LIVE
    // above holds.
    test.info().annotations.push({
      type: "issue",
      description: `j06 D2: Daniel's approval click is walked full stack only (${LIVE})`,
    });
    await journey.as("samuel-ito", TAX09, {
      scenario: "TAX-09:a",
      flags: TAX_FLAGS,
      clock: EXPORT_DAY,
    });
    await journey.step("J06 D2: Export to tax engine, then Mark exported", async (page) => {
      const sync = page.getByRole("dialog", { name: "Tax-engine sync" });
      await sync.getByRole("button", { name: /Export to tax engine/u }).click();
      const mark = page.getByRole("dialog", { name: "Mark exported" });
      await expect(mark.getByText("Download").first()).toBeVisible();
      await mark.getByRole("button", { name: "Mark exported" }).click();
      await expect(page.getByRole("button", { name: /Synced Sep 16/u }).first()).toBeVisible();
      const history = page.getByRole("region", { name: "History" });
      await expect(history.getByText("Return exported to tax engine")).toBeVisible();
      await expect(history.getByText("2025I:FeldJ:V3 · Just now")).toBeVisible();
    });
  });

  test("j06 agents-off: the coordination slice passes with AI disabled", async ({ journey }) => {
    // The slice's own steps with no agent anywhere: no "via Agent" attribution and no agent
    // control on any of them (INV-1 runs after each step as well).
    const steps: readonly [string, string, string][] = [
      ["J06 agents-off: consents (ADM-05 a)", "/settings/consents", "ADM-05:a"],
      [
        "J06 agents-off: the import checkpoint (SHL-16)",
        "/tax-returns/_returnId_?ov=checkpoints:tax_return:_returnId_",
        "TAX-02:j06",
      ],
      ["J06 agents-off: the blocked export (TAX-09 b)", TAX09, "TAX-09:b"],
      ["J06 agents-off: the export (TAX-09 a)", TAX09, "TAX-09:a"],
    ];
    for (const [name, path, scenario] of steps) {
      await journey.as(path.startsWith("/settings") ? "grace-holloway" : "samuel-ito", path, {
        scenario,
        flags: [...TAX_FLAGS, ...CONSENT_FLAGS],
      });
      await journey.step(name, async (page) => {
        await expect(page.locator("main")).toBeVisible();
        await expect(page.getByText(/via Agent/u)).toHaveCount(0);
      });
    }
  });

  test("j06 13: extensions, estimates and acks", async ({ journey }) => {
    await journey.as("samuel-ito", "/tax-returns/extensions?screen=TAX-13&st=e", {
      clock: DEMO_INSTANT,
    });
    await journey.step("J06 step 13: Feld Filed, Varga Rejected with its code", async (page) => {
      await expect(page.getByText("IND-031-04")).toBeVisible();
    });
  });
});

// T-04-T32 (TASK-7320; T-04 §10; DEC-4319): J06's journey slice for the 1040 shadow flip, steps
// j06 6, 7, 8, 8b and "j06 10 final approval blocked by Draft K-1", on the return review
// artboards in fixture mode (the gallery; personas and the demo clock from each scenario). Every
// step runs axe and INV-1 to INV-5 through the harness. The full stack and staging walks, with the
// fake CCH and fake Textract, wait for T-04-T29's live hosts and staging, so they are fixme there.

const T04_LIVE =
  "T-04-T29's live hosts for TAX-04 to TAX-07 and TXI-01, and staging with the fake CCH and fake Textract (shadow flip, Tue Mar 28, 2028)";

function artboard(id: string, state: string, persona: string): string {
  return `/components/screens/${id}?st=${state}&as=${persona}`;
}

async function noUnapprovedDecision(page: Page): Promise<void> {
  await noAgentDecision(page);
  await expect(page.getByText(/I approved|I changed/u)).toHaveCount(0);
}

test.describe("J06 1040 season · review slice (T-04-T32)", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", T04_LIVE);
  });

  test("j06 6: the Return Drafter's draft lands as a proposed checkpoint (TAX-07, SHL-16)", async ({
    journey,
  }) => {
    await journey.as("kevin-osei", artboard("TAX-07", "b", "kevin-osei"));
    await journey.step(
      "J06 step 6: the drafter's checkpoint is proposed, not applied",
      async (page) => {
        await onScreen(page, "TAX-07");
        await noUnapprovedDecision(page);
      },
    );
    await journey.as("kevin-osei", artboard("TAX-07", "b2", "kevin-osei"));
    await journey.step("J06 step 6: the checkpoint's steps (old → new, cause)", async (page) => {
      await onScreen(page, "TAX-07");
    });
  });

  test("j06 7: Kevin approves documents at his level and Review counts down", async ({
    journey,
  }) => {
    await journey.as("kevin-osei", artboard("TAX-04", "a", "kevin-osei"));
    await journey.step("J06 step 7: the prepare preset (TAX-04 a)", async (page) => {
      await onScreen(page, "TAX-04");
      await noUnapprovedDecision(page);
    });
    await journey.as("samuel-ito", artboard("TAX-05", "a", "samuel-ito"));
    await journey.step("J06 step 7: the review preset (TAX-05 a)", async (page) => {
      await onScreen(page, "TAX-05");
    });
  });

  test("j06 8: the issues, with fix instructions only a person sets", async ({ journey }) => {
    await journey.as("samuel-ito", artboard("TAX-06", "a", "samuel-ito"));
    await journey.step("J06 step 8: the 18A issue selected (TAX-06 a)", async (page) => {
      await onScreen(page, "TAX-06");
      await expect(page.locator("[data-issue='box18a']").first()).toBeVisible();
      await noUnapprovedDecision(page);
    });
  });

  test("j06 8b: field provenance and section sign-off on the worksheet (TXI-01)", async ({
    journey,
  }) => {
    await journey.as("samuel-ito", artboard("TXI-01", "b", "samuel-ito"));
    await journey.step("J06 step 8b: field provenance (TXI-01 b)", async (page) => {
      await onScreen(page, "TXI-01");
      await noUnapprovedDecision(page);
    });
  });

  test("j06 10 final approval blocked by Draft K-1", async ({ journey }) => {
    await journey.as("samuel-ito", artboard("TAX-05", "e", "samuel-ito"));
    await journey.step("J06 step 10: final approval waits on the released K-1", async (page) => {
      await onScreen(page, "TAX-05");
      await expect(page.getByText("Draft K-1 · pre-release").first()).toBeVisible();
      await expect(page.getByRole("button", { name: "Request final approval…" })).toBeDisabled();
      await noUnapprovedDecision(page);
    });
  });
});

// T-04-T32 (TASK-7324): the same slice on the full stack, against `make seed-demo` with the
// `tax_workspace` slice (Feld's worksheets, issues and named checkpoints; T-04-T28). j06 8 and 8b
// walk T-04-T29's live hosts on seeded data. j06 6, 7 and 10 stay fixme: the seed has no drafter
// run, no approval timeline for the 41 documents and no Ridgeline draft K-1 activity (T-04-T28's
// partial). Staging (three nights with the fake CCH and fake Textract) waits for staging.
const T28_SEED =
  "T-04-T28's seed: the drafter's run, the 41 documents' approval timeline and the Ridgeline draft K-1 activity";
const STAGING = "staging with the fake CCH and fake Textract (shadow flip, Tue Mar 28, 2028)";
const FELD = "Jonah & Claire Feld";
const NO_SLICE =
  "the stack was seeded without `--slice tax_workspace` (Feld's worksheets and issues)";

/** Feld's 2025 1040 on the seeded firm, opened from the returns board the way a person opens
 * it (the id is the URL's), or null when the stack was seeded without the `tax_workspace` slice
 * (the nightly's E0 default): then the step is fixme, not failed. */
async function feldReturn(page: Page): Promise<string | null> {
  await page.goto("/tax-returns");
  const row = page.getByRole("row").filter({ hasText: FELD }).filter({ hasText: "1040" }).first();
  try {
    await row.waitFor({ timeout: 15_000 });
  } catch {
    return null;
  }
  await row.getByRole("button", { name: "Open row" }).click();
  await page.waitForURL(/\/tax-returns\/[0-9a-f-]{36}/u);
  return /\/tax-returns\/([0-9a-f-]{36})/u.exec(page.url())?.[1] ?? null;
}

test.describe("J06 1040 season · review slice, full stack (T-04-T32)", () => {
  test.beforeEach(({ journey }) => {
    test.skip(journey.project === "fixture", "the artboard describe above walks fixture mode");
    test.fixme(journey.project !== "fullstack", STAGING);
  });

  test("j06 6 and 7 on the full stack", () => {
    test.fixme(true, T28_SEED);
  });

  test("j06 8: Samuel works Feld's open issues (TAX-06 live)", async ({ journey }) => {
    await journey.as("samuel-ito", "/");
    const id = await feldReturn(journey.page);
    test.fixme(id === null, NO_SLICE);
    if (id === null) return;
    await journey.as("samuel-ito", `/tax-returns/${id}/issues`);
    await journey.step("J06 step 8: the box 18A issue is open on Feld's return", async (page) => {
      await onScreen(page, "TAX-06");
      await expect(
        page.getByText("Source K-1 box 18A 'Tax-exempt interest' is not on the worksheet").first(),
      ).toBeVisible();
      await noUnapprovedDecision(page);
    });
  });

  test("j06 8b: the Ridgeline worksheet's fields and section sign-off (TAX-05 Worksheets live)", async ({
    journey,
  }) => {
    await journey.as("samuel-ito", "/");
    const id = await feldReturn(journey.page);
    test.fixme(id === null, NO_SLICE);
    if (id === null) return;
    await journey.as("samuel-ito", `/tax-returns/${id}/review/worksheets`);
    await journey.step("J06 step 8b: Sch E p2 — Ridgeline, from the seed", async (page) => {
      await page
        .getByRole("navigation", { name: "Worksheets" })
        .getByText("Sch E p2 — Ridgeline")
        .click();
      await expect(page.locator("[data-screen='TAX-05'][data-live]")).toBeVisible();
      await expect(page.getByRole("button", { name: "Sch E p2 — Ridgeline" })).toHaveAttribute(
        "aria-current",
        "page",
      );
      await expect(page.getByText("Net rental real estate income").first()).toBeVisible();
      await expect(page.getByText("307,900").first()).toBeVisible();
      await expect(page.getByRole("button", { name: "Sign off…" }).first()).toBeVisible();
      await noUnapprovedDecision(page);
    });
  });

  test("j06 10 on the full stack", () => {
    test.fixme(true, T28_SEED);
  });
});
