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
// POR-01 e's reminder link, issued Aug 20 and past its 14 days (fixtures/scenarios/POR-01.ts).
const EXPIRED_LINK = "fixture-reminder-link-feld-2026-08-20";

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

  // P-08-T26: the sign-in's other paths, in the fixture project on POR-01's own scenarios (`?st=`);
  // the full stack and staging need the emailed code from the sink mailbox (F-04-T22).
  test("J12 2b: Tess Moreno signs in with the emailed code and her authenticator (POR-01c, POR-02d)", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", "the codes come from the sink mailbox (F-04-T22)");
    await journey.as("tess-moreno", "/sign-in?st=c", { clock: SIGN_IN_CLOCK });
    const page = journey.page;
    await page.getByLabel("Email").fill("tess.moreno@sink.brightwaterhale.test");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.locator("input[autocomplete='one-time-code']").first().focus();
    await page.keyboard.type("481027");
    await journey.step("J12 step 2b: the second step (POR-01c)", async () => {
      await expect(page.getByRole("heading", { name: "Two-step verification" })).toBeVisible();
    });
    await page.getByRole("group", { name: "Authenticator code" }).locator("input").first().focus();
    await page.keyboard.type("481027");
    await page.getByRole("button", { name: "Verify" }).click();
    await journey.step("J12 step 2b: Tess's home (POR-02d)", async () => {
      await expect(page.getByRole("heading", { name: "Good morning, Tess" })).toBeVisible();
      await expect(page.getByText(/accrued/i)).toHaveCount(0);
    });
  });

  test("J12 1e: an expired sign-in link is renewed by email (POR-01e)", async ({ journey }) => {
    test.fixme(journey.project !== "fixture", "the link comes from the sink mailbox (F-04-T22)");
    await journey.as("claire-feld", `/sign-in?st=e#link=${EXPIRED_LINK}`, {
      clock: SIGN_IN_CLOCK,
    });
    await journey.step("J12 step 1e: the expired link (POR-01e)", async (page) => {
      // The emailed link opens the card with its token; Continue asks for it and finds it expired.
      await page.getByLabel("Email").fill("claire.feld@sink.brightwaterhale.test");
      await page.getByRole("button", { name: "Continue" }).click();
      await expect(
        page.getByRole("heading", { name: "This sign-in link has expired" }),
      ).toBeVisible();
      await page.getByRole("button", { name: "Email me a new link" }).click();
      await expect(
        page.getByText("New link sent to claire.feld@sink.brightwaterhale.test"),
      ).toBeVisible();
    });
  });

  test("J12 1g: too many wrong codes pause sign-in and name the firm's contact (POR-01g)", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", "the codes come from the sink mailbox (F-04-T22)");
    await journey.as("claire-feld", "/sign-in?st=g", { clock: SIGN_IN_CLOCK });
    const page = journey.page;
    await page.getByLabel("Email").fill("claire.feld@sink.brightwaterhale.test");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.locator("input[autocomplete='one-time-code']").first().focus();
    await page.keyboard.type("481072"); // a mistyped code, on the last try
    await journey.step("J12 step 1g: Too many attempts (POR-01g)", async () => {
      await expect(page.getByRole("heading", { name: "Too many attempts" })).toBeVisible();
      await expect(page.getByText(/contact Grace Holloway at Brightwater Hale/)).toBeVisible();
    });
  });

  test("J12 role union: Meera Shah's home and her scopes, each with its role (POR-02e)", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", "the role union's homes are P-08-T23's fixtures");
    await journey.as("meera-shah", "/", { clock: DEMO_INSTANT });
    await journey.step("J12 role union: Meera's own 1040 (POR-02e)", async (page) => {
      await expect(page.getByRole("heading", { name: "Good morning, Meera" })).toBeVisible();
    });
    await journey.step("J12 role union: her scopes in the account menu", async (page) => {
      await page.getByRole("button", { name: /Meera Shah/ }).click();
      const menu = page.getByRole("menu", { name: "Account" });
      await expect(menu.getByRole("menuitemradio", { name: /Meera Shah/ })).toBeVisible();
      await expect(
        menu.getByRole("menuitemradio", { name: /Ridgeline Property Partners, LP/ }),
      ).toBeVisible();
      // Closed before the step's axe pass: the open menu is modal, so it hides the page behind it
      // (aria-hidden on #root while focus stays in the menu), which axe reads as aria-hidden-focus.
      await page.keyboard.press("Escape");
      await expect(menu).toHaveCount(0);
    });
  });

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
