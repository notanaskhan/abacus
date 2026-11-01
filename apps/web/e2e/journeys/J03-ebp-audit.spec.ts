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
