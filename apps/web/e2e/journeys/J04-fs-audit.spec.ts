// J04-fs-audit, PBC slice (F-04-T32; F-04.33; blueprint §7.4): Granite Peak Outdoor Supply's FY2026
// financial statement audit asks for a document, Luis Ferrante (Granite Peak's CFO) uploads it in
// the portal, the upload is scanned and screened, and the staff accept it or return it. The slice
// runs at the Sep 24 snapshot (F-04.18: Granite Peak's fieldwork), which the Pilot 0 sessions load.
// Walkable steps run on the harness in every project (axe and INV-1 to INV-5 after each step); a
// step whose screen or backend is still planned is `test.fixme` naming its owning epic, task and
// chapter 01 date (journey-e2e skill), never skipped or left out. Walkable on staging by M6 (Fri
// Mar 5, 2027). The portal is white-labelled: no portal step may show the product's name (INV-4).
import { expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
// The Sep 24 snapshot's instant (backend epochs.py: 2026-09-24 09:00 CT).
const SEP_24 = "2026-09-24T09:00:00-05:00";
const GRANITE_PEAK = "Granite Peak Outdoor Supply, Inc.";

// Node's Buffer at run time (the workspace has no @types/node; node-shim.d.ts declares the type).
const nodeBuffer = (globalThis as unknown as { Buffer: { from(text: string): Buffer } }).Buffer;

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("J04-fs-audit PBC slice", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    // Hosted projects run only from the jobs that set their URL (F-04-T28; staging is not up yet).
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
  });

  test("J04 pbc 1: Luis Ferrante opens Granite Peak's portal sign-in (POR-01a)", async ({
    journey,
  }) => {
    await journey.as("luis-ferrante", "/sign-in", { clock: SEP_24 });
    await journey.step("J04 pbc step 1: portal sign-in as Luis Ferrante", async (page) => {
      await expect(
        page.getByRole("heading", { name: "Sign in to your client portal" }),
      ).toBeVisible();
      await expect(page.getByText(/accrued/i)).toHaveCount(0);
    });
  });

  test.fixme(
    "J04 pbc 2: Hannah Leclerc asks Granite Peak for the bank statements from the binder (BND-02, SHL-14)",
    owner("P-06 · P-06-T16 BND-02 fixture-to-live swap, binders.engine on · S6, Fri Jan 22, 2027"),
    async ({ journey }) => {
      await journey.as("hannah-leclerc", "/binders", { clock: SEP_24 });
      await journey.step("J04 pbc step 2: Granite Peak's binder", async (page) => {
        await expect(page.getByText(GRANITE_PEAK).first()).toBeVisible();
      });
    },
  );

  // R-01-T21: the client steps of the PBC slice on POR-04, at 1400 and on the 390 preset. Granite
  // Peak's binder exists only in the Sep 24 snapshot (no fixture scenario carries it, and none may
  // be invented), and the portal persona signs in through the portal BFF (P-08-T10), so the step
  // runs where both are present.
  for (const width of [1400, 390] as const) {
    test(
      `J04 pbc 3: Luis Ferrante uploads the statement against its request (POR-03, POR-04)${width === 390 ? " · 390" : ""}`,
      owner("R-01 · R-01-T21 Playwright (POR-04) · S10, Fri Mar 19, 2027"),
      async ({ journey }) => {
        test.fixme(
          journey.project === "fixture",
          "Granite Peak's binder is the Sep 24 snapshot's, full stack only (no fixture data)",
        );
        test.fixme(
          journey.project === "fullstack",
          "the fullstack adapter signs in firm personas only; the portal BFF sign-in is P-08-T10's",
        );
        await journey.page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
        await journey.as("luis-ferrante", "/documents", { clock: SEP_24 });
        const page = journey.page;
        await journey.step("J04 pbc step 3: Granite Peak's documents (POR-03)", async () => {
          await expect(page.locator("[data-request]").first()).toBeVisible();
          await expect(page.getByText(/accrued/i)).toHaveCount(0);
        });
        await page.locator("[data-request] [data-open-title]").first().click();
        const sheet = page.getByRole("dialog");
        await journey.step(
          "J04 pbc step 3: the request sheet (POR-04a)",
          async () => {
            await expect(sheet.getByRole("heading").first()).toBeVisible();
            await expect(sheet.getByText(/accrued/i)).toHaveCount(0);
          },
          { include: "[role='dialog']" },
        );
        await sheet.locator("input[type='file']").setInputFiles({
          name: "Granite_Peak_Bank_Statement_Dec_2026.pdf",
          mimeType: "application/pdf",
          buffer: nodeBuffer.from("%PDF-1.7"),
        });
        await journey.step(
          "J04 pbc step 3: the upload is received (POR-04c)",
          async () => {
            await expect(sheet.getByText(/^✓ You uploaded/)).toBeVisible();
          },
          { include: "[role='dialog']" },
        );
      },
    );
  }

  test.fixme(
    "J04 pbc 4: the upload is scanned and lands as Uploaded – needs review (POR-03c)",
    owner("R-01 · R-01-T10 drop with the scan's sorted state · S8, Fri Feb 19, 2027"),
    async ({ journey }) => {
      await journey.as("luis-ferrante", "/documents", { clock: SEP_24 });
    },
  );

  test.fixme(
    "J04 pbc 5: the screening shows its checks to Grace Holloway (SHL-20)",
    owner("P-06 · P-06-T22 SHL-20 states a-f on the screening aggregate · S8, Fri Feb 19, 2027"),
    async ({ journey }) => {
      await journey.as("grace-holloway", "/binders", { clock: SEP_24 });
    },
  );

  test.fixme(
    "J04 pbc 6: Grace accepts the statement, or returns it with a reason the client reads (SHL-20)",
    owner("P-06 · P-06-T22 SHL-20 accept and ReturnDialog · S8, Fri Feb 19, 2027"),
    async ({ journey }) => {
      await journey.as("grace-holloway", "/binders", { clock: SEP_24 });
    },
  );
});

// A-01-T26: j04 1 on AUD-01's own scenario in the fixture project; full stack and staging after the
// batch deploy (A-01 §10, M6).
test.describe("J04-fs-audit (A-01's audits index)", () => {
  test("j04 1: Hannah finds Granite Peak on AUD-01 and opens its cockpit", async ({ journey }) => {
    test.fixme(
      journey.project !== "fixture",
      "audits.cockpit on in E0 and the S12 batch deployed (A-01 §10; M6, Fri Mar 5, 2027)",
    );
    await journey.as("hannah-leclerc", "/audits", { scenario: "AUD-01:a", clock: SEP_24 });
    await journey.step("J04 step 1: Granite Peak on the audits index (AUD-01 a)", async (page) => {
      await page
        .getByRole("link", { name: new RegExp(GRANITE_PEAK.split(",")[0] ?? "Granite") })
        .first()
        .click();
      await expect(page).toHaveURL(/\/audits\/[^/]+/);
    });
  });
});
