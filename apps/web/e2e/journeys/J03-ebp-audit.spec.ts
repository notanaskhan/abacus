// J03-ebp-audit (blueprint §7.3): Northwind Robotics 401(k) Plan's PY2025 employee benefit plan
// audit. This file starts with R-01's portal steps (R-01-T21; R-01 §10): 4c (Dana Kowalski sees only
// her own requests on POR-03 i; Sam Ortiz, Keystone's contact, sees his room on POR-14 a) and 10
// (Marcus Delaney delegates the bridge letter to Sam, who uploads it in his room). A-01-T26 adds
// the firm's steps (4e, 5, 5c). P-06-T25 adds the binder's: 4 (Marcus composes the ERISA fidelity
// bond request, SHL-14 a) and 10 from the binder (the bridge letter delegated to Sam, SHL-14 b),
// walked in the fixture project on SHL-14's own scenarios (`?screen=`, G-01-T16). Walkable steps run on the harness in every project (axe and INV-1
// to INV-5 after each step); a step whose screen or backend is still planned is `test.fixme`
// naming its owning epic, task and chapter 01 date (journey-e2e skill). The portal is
// white-labelled: no portal step may show the product's name (INV-4).
import type { Page } from "@playwright/test";
import { DEMO_INSTANT, expect, test } from "../harness";
import { M13, artboard } from "../signatures/support";
import { artboardAs, board, noProductName, owner as r02Owner } from "./r02-support";
import { A07_LIVE, a07, noAgentDecision, onScreen } from "./a07-support";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const BRIDGE = "Bridge letter — Oct 1 to Dec 31, 2025";

// Node's Buffer at run time (the workspace has no @types/node; node-shim.d.ts declares the type).
const nodeBuffer = (globalThis as unknown as { Buffer: { from(text: string): Buffer } }).Buffer;

const LIVE = "binders.engine is off in E0; the BND-02 and SHL-14 live swap is P-06-T16's";
const FLAGS = ["binders.engine"];

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("J03-ebp-audit (R-01's portal steps)", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    // Hosted projects run only from the jobs that set their URL (F-04-T28; staging is not up yet).
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
  });

  for (const width of [1400, 390] as const) {
    const at = width === 390 ? " · 390" : "";

    test(
      `J03 4c: Dana Kowalski sees only her own Northwind requests (POR-03i)${at}`,
      owner("R-01 · R-01-T21 Playwright (POR-03 i) · S10, Fri Mar 19, 2027"),
      async ({ journey }) => {
        test.fixme(journey.project !== "fixture", "the portal sign-in BFF is P-08-T10's (S6)");
        await journey.page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
        await journey.as("dana-kowalski", "/documents", { clock: DEMO_INSTANT });
        const page = journey.page;
        await journey.step(
          "J03 step 4c: Dana's requests in folder bands (POR-03i)",
          async () => {
            await expect(page.getByText("Employee census file — 2025").first()).toBeVisible();
            await expect(
              page.getByText(
                "Some requests go to Keystone, Harborline, PayGrid and Summit directly.",
              ),
            ).toBeVisible();
            await expect(page.getByText(/accrued/i)).toHaveCount(0);
          },
          // INV-4: the delegated organisations are named, never their requests.
          { outOfScope: [BRIDGE] },
        );
      },
    );

    test(
      `J03 4c: Sam Ortiz sees only Keystone's requests in his room (POR-14a)${at}`,
      owner("R-01 · R-01-T21 Playwright (POR-14 a) · S10, Fri Mar 19, 2027"),
      async ({ journey }) => {
        test.fixme(journey.project !== "fixture", "the portal sign-in BFF is P-08-T10's (S6)");
        await journey.page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
        await journey.as("sam-ortiz", "/requests", { clock: DEMO_INSTANT });
        const page = journey.page;
        await journey.step(
          "J03 step 4c: Sam's room (POR-14a)",
          async () => {
            await expect(page.getByText("4 of 9 uploaded").first()).toBeVisible();
            await expect(page.getByText(/accrued/i)).toHaveCount(0);
          },
          { outOfScope: ["Employee census file — 2025"] },
        );
      },
    );
  }

  test.fixme(
    "J03 10: Marcus Delaney delegates the bridge letter to Sam Ortiz from AUD-03 (Request from third party…)",
    owner("A-01 · A-01-T26 journey E2E on AUD-03 · S12, Fri Apr 16, 2027"),
    async ({ journey }) => {
      await journey.as("marcus-delaney", "/audits", { clock: DEMO_INSTANT });
    },
  );

  test(
    "J03 10: Sam Ortiz uploads the bridge letter in his room, which reads in review (POR-14a → b)",
    owner("R-01 · R-01-T21 Playwright (POR-14) · S10, Fri Mar 19, 2027"),
    async ({ journey }) => {
      test.fixme(journey.project !== "fixture", "the portal sign-in BFF is P-08-T10's (S6)");
      await journey.as("sam-ortiz", "/requests", { clock: DEMO_INSTANT });
      const page = journey.page;
      await page.getByText("4 of 9 uploaded").first().waitFor();
      // /requests opens with every row folded (POR-14: a row click expands it in-screen).
      await page.getByRole("button", { name: new RegExp(`^${BRIDGE}`) }).click();
      await page
        .getByRole("button", { name: /Drop the letter here or Upload…/ })
        .first()
        .click();
      await page
        .locator("[data-room] input[type='file']")
        .first()
        .setInputFiles({
          name: "Keystone_Bridge_Letter.pdf",
          mimeType: "application/pdf",
          buffer: nodeBuffer.from("%PDF-1.4"),
        });
      await journey.step("J03 step 10: the bridge letter in review (POR-14b)", async () => {
        await expect(page.getByText("5 of 9 uploaded").first()).toBeVisible();
        await expect(page.getByText(/accrued/i)).toHaveCount(0);
      });
    },
  );
});

/** The composer's menu field (`Category`, `Client assignee`, `Third party`): open it, pick one. */
async function choose(page: Page, label: RegExp, option: string): Promise<void> {
  const drawer = page.getByRole("dialog");
  await drawer.getByRole("button", { name: label }).focus();
  await page.keyboard.press("ArrowDown");
  await page.getByRole("menu").getByText(option, { exact: true }).click();
}

test.describe("J03-ebp-audit (P-06's binder steps)", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", LIVE);
  });

  test("j03 4: Marcus composes the ERISA fidelity bond request and Hannah publishes the PBC binder", async ({
    journey,
  }) => {
    await journey.as("marcus-delaney", "/binders/_binderId_?ov=request:new:_binderId_", {
      scenario: "SHL-14:a",
      flags: FLAGS,
    });
    await journey.step(
      "J03 step 4: the composer, a new request on the Northwind binder (SHL-14a)",
      async (page) => {
        await expect(page.getByRole("heading", { name: "New request" })).toBeVisible();
        await expect(page.getByRole("dialog").getByLabel("Due")).toHaveValue("2026-09-21");
      },
    );
    await journey.step(
      "J03 step 4: Marcus writes it and sends, a person's click",
      async (page) => {
        const drawer = page.getByRole("dialog");
        await drawer
          .getByLabel("Request", { exact: true })
          .fill("ERISA fidelity bond — 2025 declarations page");
        await drawer
          .getByLabel("Description")
          .fill(
            "ERISA §412 requires a fidelity bond of at least 10% of plan assets handled, capped at $500,000 for this plan.",
          );
        await choose(page, /^Category/, "Plan documents");
        await choose(page, /^Client assignee/, "Dana Kowalski");
        await drawer.getByRole("button", { name: "Save & send" }).click();
        await expect(page.getByText("Request sent to Dana Kowalski").first()).toBeVisible();
      },
    );
  });

  test.fixme(
    "j03 4 (publish): Hannah publishes the Northwind PBC binder",
    owner(
      "P-06 · P-06-T16 BND-02 live swap: the fixtures publish only the Feld binder (BND-02 b → a), not a Northwind PBC Draft · S6, Fri Jan 22, 2027",
    ),
    async ({ journey }) => {
      await journey.as("hannah-leclerc", "/binders", { flags: FLAGS });
    },
  );

  test("j03 10: the bridge-letter request is delegated to Sam Ortiz and scoped to one request", async ({
    journey,
  }) => {
    await journey.as("marcus-delaney", "/binders/_binderId_?ov=request:_requestId_:_binderId_", {
      scenario: "SHL-14:b",
      flags: FLAGS,
    });
    await journey.step(
      "J03 step 10: the bridge letter, requested Sep 1 (SHL-14b)",
      async (page) => {
        const drawer = page.getByRole("dialog");
        await expect(drawer.getByText("Requested Sep 1 · due Sep 25")).toBeVisible();
        await expect(drawer.getByLabel("Request", { exact: true })).toHaveValue(
          "Bridge letter — Keystone, Oct–Dec 2025",
        );
      },
    );
    await journey.step("J03 step 10: delegated to Sam Ortiz, this request only", async (page) => {
      const drawer = page.getByRole("dialog");
      await drawer.getByRole("switch", { name: "Request from a third party" }).click();
      await choose(page, /^Third party/, "Sam Ortiz");
      await expect(
        drawer.getByText("Sam sees only this request (POR-14). Dana is copied."),
      ).toBeVisible();
      await expect(drawer.getByRole("button", { name: "Save & send to Sam Ortiz" })).toBeVisible();
    });
  });
});

// A-01-T26 (A-01 §10): the firm's Source Documents steps on AUD-03, walked in the fixture project on
// AUD-03's own scenarios (`?screen=AUD-03&st=…`, the audit and row from its ids). Full stack and
// staging walk them once `audits.cockpit` is on in E0 and the batch is deployed (A-01 §10, M6).
test.describe("J03-ebp-audit (A-01's Source Documents steps)", () => {
  const SOURCE = "/audits/_auditId_/source-documents?item=_itemId_";

  test.beforeEach(({ journey }) => {
    test.fixme(
      journey.project !== "fixture",
      "audits.cockpit on in E0 and the S12 batch deployed (A-01 §10; M6, Fri Mar 5, 2027)",
    );
  });

  test("j03 4e: Marcus opens a requested row and drafts a reminder to Dana that only a person sends", async ({
    journey,
  }) => {
    await journey.as("marcus-delaney", SOURCE, { scenario: "AUD-03:e", clock: DEMO_INSTANT });
    await journey.step(
      "J03 step 4e: a requested row on Source Documents (AUD-03 e)",
      async (page) => {
        await expect(page.getByRole("button", { name: "Remind…" }).first()).toBeVisible();
      },
    );
    await journey.step("J03 step 4e: the reminder is drafted, a person sends it", async (page) => {
      await page.getByRole("button", { name: "Remind…" }).first().click();
      const sheet = page.getByRole("dialog");
      await expect(sheet).toBeVisible();
      // The agent may draft; only a person's click sends (INV-1, ADR-005).
      await expect(sheet.getByRole("button", { name: /^Send/ })).toBeVisible();
    });
  });

  test("j03 5: Ana accepts the certified trust report and Source Documents reads 12 of 24", async ({
    journey,
  }) => {
    await journey.as("ana-cruz", SOURCE, { scenario: "AUD-03:b", clock: DEMO_INSTANT });
    await journey.step(
      "J03 step 5: the certified trust report in the dock (AUD-03 b)",
      async (page) => {
        await expect(page.getByRole("button", { name: "Accept", exact: true })).toBeVisible();
      },
    );
    await journey.step("J03 step 5: Ana accepts it", async (page) => {
      await page.getByRole("button", { name: "Accept", exact: true }).click();
      await expect(page.getByText(/accepted$/).first()).toBeVisible();
      await expect(page.getByText(/12 of 24/).first()).toBeVisible();
    });
  });

  test("j03 5c: the 62% BrokerWindow match is held and Ana returns it as Wrong document", async ({
    journey,
  }) => {
    await journey.as("ana-cruz", SOURCE, { scenario: "AUD-03:c", clock: DEMO_INSTANT });
    await journey.step("J03 step 5c: the held 62% match (AUD-03 c)", async (page) => {
      await expect(page.getByText(/match 62%/).first()).toBeVisible();
    });
    await journey.step("J03 step 5c: Ana returns it as Wrong document", async (page) => {
      await page
        .getByRole("button", { name: /^Return/ })
        .first()
        .click();
      const dialog = page.getByRole("dialog");
      await dialog.getByText("Wrong document", { exact: true }).click();
      await dialog.getByRole("button", { name: /^Return/ }).click();
      await expect(dialog).toBeHidden();
    });
  });

  test("j03 6 (host): AUD-02 opens from AUD-01 at Source Documents", async ({ journey }) => {
    await journey.as("ana-cruz", "/audits", { scenario: "AUD-01:a", clock: DEMO_INSTANT });
    await journey.step("J03 step 6: the audits index (AUD-01 a)", async (page) => {
      // AUD-01 rows open through their "Open row" button; the engagement name is a cell.
      await expect(page.getByRole("row", { name: /Northwind/ }).first()).toBeVisible();
    });
  });

  test.fixme(
    "j03 6 (dock): the dock steps",
    owner("P-09/P-10 · SHL-13 · S16, Tue Jun 1, 2027"),
    async ({ journey }) => {
      await journey.as("ana-cruz", "/audits", { clock: DEMO_INSTANT });
    },
  );
});

// N-02-T42 (N-02 §10.1, M13): j03 3, the audit engagement letter through POR-06 to G3. The fixture
// walk uses the built artboards: ENG-04 e (the EBP audit letter variant, sent, 0 of 2 signed) and
// Dana Kowalski's Sign area (POR-06). The Northwind letter itself walks on staging (M13).
test.describe("J03 signatures (N-02-T42)", () => {
  test("j03 3: Hannah sends the audit letter and Dana signs (G3)", async ({ journey }) => {
    test.fixme(journey.project !== "fixture", M13);
    await journey.as("hannah-leclerc", artboard("ENG-04", "e"));
    await journey.step("j03 3: the EBP audit letter, sent (ENG-04 e)", async (page) => {
      await expect(page.getByText(/^Sent .* · 0 of 2 signed$/).first()).toBeVisible();
    });
    await journey.as("dana-kowalski", "/sign", { scenario: "POR-06:list" });
    await journey.step("j03 3: Dana's Sign area (POR-06)", async (page) => {
      await expect(page.getByRole("heading", { name: /Sign/ }).first()).toBeVisible();
      await expect(page.getByText(/Accrued/)).toHaveCount(0);
    });
  });
});

// A-04-T34 (TASK-3285): J03 planning steps 8 to 10b in fixture mode, each step with axeStep and
// assertInvariants (the journey harness). The register and the IC pack failure walk their screens'
// own scenarios on Northwind's audit; steps whose screen or backend is not live yet are fixme with
// the epic that lands them.
test.describe("J03 planning (A-04-T34)", () => {
  const RISKS = "/audits/_auditId_/risks";
  const CONTROLS = "/audits/_auditId_/controls";

  test.fixme(
    "j03 8: Margaret decides materiality v2 on SHL-11 (AUD-07 d)",
    owner("A-04 · AUD-07 is a cockpit section with no route of its own (DEC-1865) · P-10 run"),
    async ({ journey }) => {
      await journey.as("margaret-okonkwo", "/audits", { clock: DEMO_INSTANT });
    },
  );

  test("j03 9: the risk register is EP approved and G4 met (AUD-08 d)", async ({ journey }) => {
    test.fixme(journey.project !== "fixture", "AUD-08 live swap is A-04-T29's staging walk");
    await journey.as("hannah-leclerc", RISKS, { scenario: "AUD-08:d", clock: DEMO_INSTANT });
    await journey.step("J03 step 9: every risk EP approved (AUD-08 d)", async (page) => {
      await expect(page.locator("[data-aud08='tally']")).toContainText("Approved");
      await expect(page.locator("[data-risk]")).toHaveCount(10);
    });
  });

  test("j03 10a: the IC pack failure quotes the run error and offers Retry (AUD-09 d)", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", "the seeded failure is the fixture's run (P-10)");
    await journey.as("hannah-leclerc", CONTROLS, { scenario: "AUD-09:d", clock: DEMO_INSTANT });
    await journey.step("J03 step 10a: the failed step and No evidence written.", async (page) => {
      await expect(page.locator("[data-aud09='run-error']")).toContainText("BH-EBP-140 step 8");
      await expect(page.locator("[data-aud09='footer']")).toHaveText("No evidence written.");
      await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
    });
  });

  test("j03 10a2: Exceptions!D2 names its two citations (AUD-09 b)", async ({ journey }) => {
    test.fixme(journey.project !== "fixture", "AUD-09 live data is A-04-T25's on staging");
    await journey.as("hannah-leclerc", CONTROLS, { scenario: "AUD-09:b", clock: DEMO_INSTANT });
    await journey.step("J03 step 10a: the D2 citations in the footer", async (page) => {
      await expect(page.locator("[data-aud09='footer']")).toContainText(
        "Exceptions!D2 · 2 citations",
      );
    });
  });

  test.fixme(
    "j03 10b: the Keystone SOC gap and the bridge letter (AUD-10)",
    owner("A-04 · AUD-10 screen (A-04-T37) · S28"),
    async ({ journey }) => {
      await journey.as("hannah-leclerc", "/audits", { clock: DEMO_INSTANT });
    },
  );

  test.fixme(
    "j03 8b: Risk Assessment adopted and the fraud minutes approved (AUD-05)",
    owner("A-04 · AUD-05 adopt walk needs P-10's run state · S28"),
    async ({ journey }) => {
      await journey.as("hannah-leclerc", "/audits", { clock: DEMO_INSTANT });
    },
  );

  test("j03 7, 7b, 12, 13: the plan's TB, profile, testing and contributions", async ({
    journey,
  }) => {
    await journey.as("marcus-delaney", "/audits/_auditId_?screen=EBP-06&st=a&section=ebp_06", {
      clock: DEMO_INSTANT,
    });
    await journey.step("J03 step 7: EBP-06 agrees the trust report", async (page) => {
      await expect(page.locator("[data-screen='EBP-06']").first()).toBeVisible();
    });
    await journey.as("marcus-delaney", "/audits/_auditId_?screen=EBP-01&st=a&section=ebp_01", {
      clock: DEMO_INSTANT,
    });
    await journey.step("J03 step 7b: the plan profile", async (page) => {
      await expect(page.locator("[data-screen='EBP-01']").first()).toBeVisible();
    });
    await journey.as("marcus-delaney", "/audits/_auditId_?screen=EBP-03&st=a&section=ebp_03", {
      clock: DEMO_INSTANT,
    });
    await journey.step("J03 step 12: eligibility testing", async (page) => {
      await expect(page.locator("[data-screen='EBP-03']").first()).toBeVisible();
    });
    await journey.as("marcus-delaney", "/audits/_auditId_?screen=EBP-04&st=a&section=ebp_04", {
      clock: DEMO_INSTANT,
    });
    await journey.step("J03 step 13: contributions and remittance", async (page) => {
      await expect(page.locator("[data-screen='EBP-04']").first()).toBeVisible();
    });
  });
});

// A-06-T35 (TASK-6121): J03 completion steps 13, 14 and 16 on AUD-15, AUD-16, AUD-17 and AUD-20
// in fixture mode, each with axeStep and assertInvariants (the journey harness). The full-stack
// run waits for A-08's AUD-26 (the cockpit's completion band on staging): fixme off fixture.
test.describe("J03 completion (A-06-T35)", () => {
  const AUDIT = "/audits/_auditId_";
  const FULL_STACK = "the full-stack run waits for A-08's AUD-26 (S35)";
  const COCKPIT = ["audits.cockpit"]; // E0 leaves the cockpit off; its fixtures turn it on

  test("j03 13: the findings and misstatements tabs read the SUM (AUD-16 a)", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", FULL_STACK);
    await journey.as("hannah-leclerc", `${AUDIT}/misstatements`, {
      scenario: "AUD-16:a",
      flags: COCKPIT,
    });
    await journey.step("J03 step 13: the summary of uncorrected misstatements", async (page) => {
      await expect(page.getByText("Summary of uncorrected misstatements").first()).toBeVisible();
    });
  });

  test("j03 14: review notes and the sign-off matrix (AUD-17 a)", async ({ journey }) => {
    test.fixme(journey.project !== "fixture", FULL_STACK);
    await journey.as("hannah-leclerc", `${AUDIT}/review-notes`, {
      scenario: "AUD-17:a",
      flags: COCKPIT,
    });
    await journey.step("J03 step 14: the sign-off matrix", async (page) => {
      await expect(page.getByText("Sign-off matrix").first()).toBeVisible();
    });
  });

  test("j03 16: the statements tie 63 of 63 and the checklist counts 142 (AUD-20 a)", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", FULL_STACK);
    await journey.as("hannah-leclerc", `${AUDIT}/fs-disclosure`, {
      scenario: "AUD-20:a",
      flags: COCKPIT,
    });
    await journey.step(
      "J03 step 16: every line ties and the checklist is 142 items",
      async (page) => {
        await expect(page.locator("[data-tie]")).toHaveText("63 of 63 tie");
        await expect(page.locator("[data-summary]")).toContainText("142 items");
      },
    );
  });
});

// A-05-T61 (TASK-6221): J03 12a (participant accounts, EBP-08) and 12b (the Form 5500 tie-out,
// EBP-07) in fixture mode on Northwind's cockpit, each with axeStep and INV-1 to INV-5 (the journey
// harness). The staging walk waits for the EBP batch's deploy and `ebp.modules` on PF-X1: fixme off
// fixture.
test.describe("J03 EBP-08 and EBP-07 (A-05-T61)", () => {
  const STAGING = "the staging walk waits for the S31 batch on staging (A-05-T61; DEC-1389 gates)";

  test("j03 12a: Hannah reads the participant accounts summary (EBP-08 a)", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", STAGING);
    await journey.as("hannah-leclerc", "/audits/_auditId_?screen=EBP-08&st=a&section=ebp_08", {
      clock: DEMO_INSTANT,
    });
    await journey.step("J03 step 12a: the participant accounts summary", async (page) => {
      await expect(page.locator("[data-screen='EBP-08']").first()).toBeVisible();
    });
  });

  test("j03 12b: the Form 5500 ties except the 48,600 receivable, and Note 8 explains it (EBP-07 a)", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", STAGING);
    await journey.as("hannah-leclerc", "/audits/_auditId_?screen=EBP-07&st=a&section=ebp_07", {
      clock: DEMO_INSTANT,
    });
    await journey.step("J03 step 12b: Schedule H against the statements", async (page) => {
      const net = page.locator("[data-line='1l']");
      await expect(net).toContainText("16,812,400");
      await expect(net).toContainText("48,600");
      await expect(page.locator("[data-ebp07='note']")).toContainText("Send note to AUD-20");
      // No "$" in the statement table (EBP-07 AVOID).
      await expect(page.locator("[data-ebp07='schedule-h']")).not.toContainText("$");
    });
    await journey.as("hannah-leclerc", "/audits/_auditId_?screen=EBP-07&st=d&section=ebp_07", {
      clock: DEMO_INSTANT,
    });
    await journey.step("J03 step 12b: before Summit's draft arrives (EBP-07 d)", async (page) => {
      await expect(page.getByText("Draft Form 5500 not received").first()).toBeVisible();
    });
  });
});

// R-02-T23 (R-02 §5.6): J03's portal halves on POR-15, POR-08 and POR-09 (fixture project); J03
// P0 lands at S36 with A-07.
test.describe("J03 · R-02 portal halves", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", "R-02's live swap (R-02-T28) and the batch deploy");
  });

  test("j03 9b: the Benefits Committee acknowledges the planning letter in the governance room", async ({
    journey,
  }) => {
    await artboardAs(journey, "victoria-lam", "POR-15", "a");
    await journey.step(
      "j03 9b: the planning letter, two of three acknowledged (POR-15 a)",
      async (page) => {
        await expect(board(page, "a").getByText("Benefits Committee").first()).toBeVisible();
        await expect(board(page, "a").getByText("Our responsibilities")).toBeVisible();
        await expect(
          board(page, "a").getByRole("button", { name: "Acknowledge", exact: true }),
        ).toBeVisible();
        await noProductName(page, "a");
      },
    );
    await artboardAs(journey, "victoria-lam", "POR-15", "b");
    await journey.step("j03 9b: acknowledged by the committee (POR-15 b)", async (page) => {
      await expect(
        board(page, "b").getByText("Acknowledged by the committee · Sep 21").first(),
      ).toBeVisible();
      await expect(
        board(page, "b").getByRole("button", { name: "Acknowledge", exact: true }),
      ).toHaveCount(0);
    });
  });

  test("j03 13: Dana accepts AJE-1 in POR-08 and the misstatement is Booked", async ({
    journey,
  }) => {
    await artboardAs(journey, "dana-kowalski", "POR-08", "e");
    await journey.step("j03 13: AJE-1 waits on Dana (POR-08 e)", async (page) => {
      await expect(board(page, "e").getByText(/AJE-1/).first()).toBeVisible();
      await expect(board(page, "e").getByText("$48,600.00").first()).toBeVisible();
    });
    await artboardAs(journey, "dana-kowalski", "POR-08", "e2");
    await journey.step("j03 13: accepted, recorded (POR-08 e2)", async (page) => {
      await expect(
        board(page, "e2")
          .getByText(/Accepted by Dana Kowalski · Sep 25/)
          .first(),
      ).toBeVisible();
    });
  });

  test.fixme(
    "j03 13 (firm half): AUD-16 shows AJE-1 Booked after Dana's acceptance",
    r02Owner(
      "A-06 · the SUM's booked state from R-02's decision event, full stack after the batch",
    ),
    async () => {},
  );

  test("j03 17: the report and FS appear Final in POR-09 and in the room's Reports", async ({
    journey,
  }) => {
    await artboardAs(journey, "dana-kowalski", "POR-09", "c");
    await journey.step("j03 17: Final documents with Download (POR-09 c)", async (page) => {
      await expect(board(page, "c").getByText("Final").first()).toBeVisible();
      await expect(
        board(page, "c").getByRole("button", { name: "Download" }).first(),
      ).toBeVisible();
    });
    await artboardAs(journey, "victoria-lam", "POR-15", "e");
    await journey.step("j03 17: the room's Reports (POR-15 e)", async (page) => {
      await expect(
        board(page, "e").getByRole("button", { name: "Download" }).first(),
      ).toBeVisible();
    });
  });

  test("j03 18: the committee acknowledges the AU-C 265/703 letter on Nov 24", async ({
    journey,
  }) => {
    await artboardAs(journey, "victoria-lam", "POR-15", "d");
    await journey.step("j03 18: the internal control letter is new (POR-15 d)", async (page) => {
      await expect(
        board(page, "d").getByText(
          "Significant deficiency — Remittance of participant contributions",
        ),
      ).toBeVisible();
      await expect(board(page, "d").getByText("Sent Nov 20 · due Dec 8")).toBeVisible();
      await expect(
        board(page, "d").getByRole("button", { name: "Acknowledge", exact: true }),
      ).toBeVisible();
    });
  });

  test("j03 privacy: Victoria Lam's answers and question stay invisible to Dana Kowalski and Robert Haines", async ({
    journey,
  }) => {
    await artboardAs(journey, "victoria-lam", "POR-15", "c");
    await journey.step(
      "j03 privacy: Victoria's two private inquiries (POR-15 c)",
      async (page) => {
        await expect(board(page, "c").getByRole("button", { name: "Send answers" })).toBeVisible();
      },
    );
    await journey.as("dana-kowalski", "/components/screens/POR-15?st=n&frame=1");
    await journey.step(
      "j03 privacy: Dana's management grant opens no room",
      async (page) => {
        await expect(page.getByRole("button", { name: "Send answers" })).toHaveCount(0);
      },
      { outOfScope: ["Victoria Lam"] },
    );
  });
});

// A-07-T50 (TASK-6820; A-07 §10 item 1): J03 completion to the locked archive, steps 9b, 15, 16,
// 17, 18 and 19, on the A-07 artboards (AUD-18, AUD-21, AUD-22, AUD-23, AUD-24, AUD-25) in fixture
// mode, each with axeStep and INV-1 to INV-5 (the journey harness). The staging walk waits for the
// S36 batch deploy and the three A-07 flags on PF-X1: fixme off fixture (A07_LIVE).
test.describe("J03 completion to archive (A-07-T50)", () => {
  test("j03 9b: Margaret approves and sends the AU-C 260 planning letter to the Benefits Committee", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", A07_LIVE);
    await journey.as("margaret-okonkwo", a07("AUD-22", "a2"));
    await journey.step(
      "j03 9b: the planning letter waits on the partner (AUD-22 a2)",
      async (page) => {
        await onScreen(page, "AUD-22");
        await expect(
          page.getByText("Our planned audit of the plan's 2025 financial statements").first(),
        ).toBeVisible();
        await noAgentDecision(page);
      },
    );
    await journey.as("hannah-leclerc", a07("AUD-22", "b"));
    await journey.step("j03 9b: sent Sep 18 and acknowledged Sep 21 (AUD-22 b)", async (page) => {
      await expect(page.getByText("Sent Sep 18").first()).toBeVisible();
      await expect(
        page.getByText("Acknowledged Sep 21 · Benefits Committee").first(),
      ).toBeVisible();
      await expect(page.getByLabel("Locked").first()).toBeVisible();
    });
  });

  test("j03 15: Thomas Whitcombe concurs and G6 is recorded; the EQR cannot sign L1–L4", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", A07_LIVE);
    await journey.as("thomas-whitcombe", a07("AUD-18", "a"));
    await journey.step(
      "j03 15: the EQR reads, with no edit or sign-off control (AUD-18 a)",
      async (page) => {
        await onScreen(page, "AUD-18");
        await expect(page.getByRole("button", { name: /^Sign off/ })).toHaveCount(0);
        await expect(page.getByRole("button", { name: /^Edit/ })).toHaveCount(0);
      },
    );
    await journey.as("thomas-whitcombe", a07("AUD-18", "c"));
    await journey.step("j03 15: concurred, G6 recorded (AUD-18 c)", async (page) => {
      // AUD-18 c (handoff spec): the green card reads the concurrence, not the card's title.
      await expect(
        page.getByText("Concurred · Oct 5, 2026", { exact: false }).first(),
      ).toBeVisible();
      await expect(page.getByText("G6 ✓").first()).toBeVisible();
      await noAgentDecision(page);
    });
    await journey.as("hannah-leclerc", a07("AUD-18", "e"));
    await journey.step(
      "j03 15: anyone but the assigned EQR cannot concur (AUD-18 e)",
      async (page) => {
        await expect(page.getByText("Only the assigned EQR can concur.").first()).toBeVisible();
      },
    );
  });

  test("j03 16: completion clears and Dana Kowalski signs the representation letter dated Oct 9, so G7 is met", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", A07_LIVE);
    await journey.as("hannah-leclerc", a07("AUD-21", "e"));
    await journey.step("j03 16: dated the report date, G7 (AUD-21 e)", async (page) => {
      await onScreen(page, "AUD-21");
      await expect(
        page.getByText("Dated October 9, 2026 = report date ✓ · G7").first(),
      ).toBeVisible();
      await noAgentDecision(page);
    });
  });

  test("j03 17: Margaret approves the report and releases on Oct 9, so G8 is recorded and POR-09 shows Final", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", A07_LIVE);
    await journey.as("margaret-okonkwo", a07("AUD-23", "b"));
    await journey.step(
      "j03 17: the report for the partner's approval (AUD-23 b)",
      async (page) => {
        await onScreen(page, "AUD-23");
        await noAgentDecision(page);
      },
    );
    await journey.as("margaret-okonkwo", a07("AUD-24", "a"));
    await journey.step(
      "j03 17: G5 to G7 met, G8 waits on the partner (AUD-24 a)",
      async (page) => {
        await expect(
          page.getByText("G8 · Released — recorded when you release").first(),
        ).toBeVisible();
        await expect(page.getByText("Reserved to the engagement partner").first()).toBeVisible();
      },
    );
    await journey.as("margaret-okonkwo", a07("AUD-24", "d"));
    await journey.step(
      "j03 17: released, G8 recorded, the archive clock starts (AUD-24 d)",
      async (page) => {
        await expect(
          page.getByText("Released Oct 9, 2026 · 10:07 AM · Margaret Okonkwo").first(),
        ).toBeVisible();
        await expect(page.getByText("Archive in 60 days · by Dec 8, 2026").first()).toBeVisible();
        await expect(
          page.getByText("Report released · delivered to Dana Kowalski").first(),
        ).toBeVisible();
      },
    );
  });

  test("j03 18: the AU-C 265/703 letter is sent Nov 20 and acknowledged Nov 24", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", A07_LIVE);
    await journey.as("hannah-leclerc", a07("AUD-22", "c"));
    await journey.step(
      "j03 18: the AU-C 265 letter with its 60-day clock (AUD-22 c)",
      async (page) => {
        await expect(
          page.getByText("Due Dec 8, 2026 · 60 days after release").first(),
        ).toBeVisible();
        await expect(page.getByText("Reportable findings (AU-C 703)").first()).toBeVisible();
      },
    );
    await journey.as("hannah-leclerc", a07("AUD-22", "e"));
    await journey.step("j03 18: sent and acknowledged (AUD-22 e)", async (page) => {
      await onScreen(page, "AUD-22");
      await noAgentDecision(page);
    });
  });

  test("j03 19: Marcus Delaney assembles, Hannah Leclerc locks on Dec 3, and a later edit is refused", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", A07_LIVE);
    await journey.as("hannah-leclerc", a07("AUD-25", "a"));
    await journey.step(
      "j03 19: 8 of 9, the lock waits on the open letter (AUD-25 a)",
      async (page) => {
        await onScreen(page, "AUD-25");
        await expect(page.getByText("8 of 9").first()).toBeVisible();
        await expect(page.getByText("47 days").first()).toBeVisible();
      },
    );
    await journey.as("hannah-leclerc", a07("AUD-25", "b"));
    await journey.step("j03 19: 9 of 9, ready to lock (AUD-25 b)", async (page) => {
      await expect(page.getByText("9 of 9").first()).toBeVisible();
    });
    await journey.as("margaret-okonkwo", a07("AUD-25", "c"));
    await journey.step("j03 19: locked with the seal, G9 (AUD-25 c)", async (page) => {
      await expect(page.getByText("Locked · sealed").first()).toBeVisible();
      await expect(
        page
          .getByText("Locked Dec 3, 2026 · 4:18 PM · Hannah Leclerc · seal 7c41…a9e2 · G9 ✓")
          .first(),
      ).toBeVisible();
      await noAgentDecision(page);
    });
    await journey.as("marcus-delaney", a07("AUD-25", "d"));
    await journey.step(
      "j03 19: a later change is a post-lock addition only (AUD-25 d)",
      async (page) => {
        await expect(page.getByText("Post-lock additions").first()).toBeVisible();
        // AUD-25 d draws the logged addition (the empty state's sentence is AUD-25 c's).
        await expect(page.getByText("Addition logged").first()).toBeVisible();
        await expect(
          page.getByText("approved by Margaret Okonkwo", { exact: false }).first(),
        ).toBeVisible();
        await expect(page.getByRole("button", { name: /^Edit/ })).toHaveCount(0);
      },
    );
  });
});
