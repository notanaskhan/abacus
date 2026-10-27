// J03-ebp-audit (blueprint §7.3): Northwind Robotics 401(k) Plan's PY2025 employee benefit plan
// audit. This file starts with R-01's portal steps (R-01-T21; R-01 §10): 4c (Dana Kowalski sees only
// her own requests on POR-03 i; Sam Ortiz, Keystone's contact, sees his room on POR-14 a) and 10
// (Marcus Delaney delegates the bridge letter to Sam, who uploads it in his room). A-01-T26 adds
// the firm's steps (4e, 5, 5c). Walkable steps run on the harness in every project (axe and INV-1
// to INV-5 after each step); a step whose screen or backend is still planned is `test.fixme`
// naming its owning epic, task and chapter 01 date (journey-e2e skill). The portal is
// white-labelled: no portal step may show the product's name (INV-4).
import { DEMO_INSTANT, expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const BRIDGE = "Bridge letter — Oct 1 to Dec 31, 2025";

// Node's Buffer at run time (the workspace has no @types/node; node-shim.d.ts declares the type).
const nodeBuffer = (globalThis as unknown as { Buffer: { from(text: string): Buffer } }).Buffer;

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
