// J12-core (F-04-T26; F-04.33; blueprint §7.12): a client signs in to the firm's portal, lands
// on their to-dos, opens their documents and uploads a file. Walkable steps run on the harness in
// every project (axe and INV-1 to INV-5 after each step); a step whose screen or backend is still
// planned is `test.fixme` naming its owning epic, task and chapter 01 date (journey-e2e skill).
// The portal is white-labelled: no step may show the product's name (INV-4).
import { DEMO_INSTANT, expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
// POR-01 a renders at 9:22 AM CT on E0's Monday (the handoff's artboard clock).
const SIGN_IN_CLOCK = "2026-09-14T09:22:00-05:00";

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("J12-core", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    // Hosted projects run only from the jobs that set their URL (F-04-T28; staging is not up yet).
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
  });

  test("J12 1: Claire Feld opens the firm's portal sign-in (POR-01a)", async ({ journey }) => {
    await journey.as("claire-feld", "/sign-in", { clock: SIGN_IN_CLOCK });
    await journey.step("J12 step 1: portal sign-in as Claire Feld", async (page) => {
      await expect(
        page.getByRole("heading", { name: "Sign in to your client portal" }),
      ).toBeVisible();
      await expect(page.getByText(/accrued/i)).toHaveCount(0);
    });
  });

  test(
    "J12 2–3: Claire types the emailed code and lands on her to-dos (POR-01b, POR-02a)",
    owner("P-08 · P-08-T10 portal sign-in BFF core · S6, Fri Jan 22, 2027"),
    async ({ journey }) => {
      // The fixture handlers answer the portal's sign-in; on the other projects the code step
      // needs the portal BFF (`/v1/portal/auth/*`), which is not built yet.
      test.fixme(journey.project !== "fixture", "the portal sign-in BFF is P-08-T10's (S6)");
      await journey.as("claire-feld", "/sign-in", { clock: SIGN_IN_CLOCK });
      const page = journey.page;
      // Any address gets the same answer (no enumeration); a synthetic one on the sink domain.
      await page.getByLabel("Email").fill("claire.feld@sink.brightwaterhale.test");
      await page.getByRole("button", { name: "Continue" }).click();
      await journey.step("J12 step 2: the code step (POR-01b)", async () => {
        await expect(page.getByRole("heading", { name: "Check your email" })).toBeVisible();
      });
      // The fixture's emailed code; the sixth digit submits.
      await page.locator("input[autocomplete='one-time-code']").first().focus();
      await page.keyboard.type("481027");
      await journey.step("J12 step 3: Claire's to-dos (POR-02a)", async () => {
        await expect(page.getByText("Upload 2 documents").first()).toBeVisible();
        await expect(page.getByText(/accrued/i)).toHaveCount(0);
      });
    },
  );

  test.fixme(
    "J12 4: Claire opens the Feld 2025 Binder's documents (POR-03a)",
    owner("R-01 · R-01-T06 POR-03 frontend part 1 · S7, Fri Feb 5, 2027"),
    async ({ journey }) => {
      await journey.as("claire-feld", "/documents", { clock: DEMO_INSTANT });
    },
  );

  test.fixme(
    "J12 5: Claire uploads a file to an open request and it is received (POR-03b, POR-04a)",
    owner("R-01 · R-01-T10 POR-03 drop and R-01-T12 POR-04 request sheet · S9, Fri Mar 5, 2027"),
    async ({ journey }) => {
      await journey.as("claire-feld", "/documents", { clock: DEMO_INSTANT });
    },
  );
});
