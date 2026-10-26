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

  // R-01-T21: steps 4, 5 and 15 at 1400 and on the 390 preset. Like 2–3, a signed-in portal step
  // runs on fixtures until the portal BFF answers on the other projects (P-08-T10).
  for (const width of [1400, 390] as const) {
    const at = width === 390 ? " · 390" : "";

    test(
      `J12 4: Claire opens the Feld 2025 Binder's documents and ignores one with a note (POR-03a, f)${at}`,
      owner("R-01 · R-01-T21 Playwright (POR-03) · S10, Fri Mar 19, 2027"),
      async ({ journey }) => {
        test.fixme(journey.project !== "fixture", "the portal sign-in BFF is P-08-T10's (S6)");
        await journey.page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
        await journey.as("claire-feld", "/documents", { clock: DEMO_INSTANT });
        const page = journey.page;
        await journey.step("J12 step 4: Claire's documents (POR-03a)", async () => {
          await expect(
            page.getByText("Form 1095-C From Mercer Hill Health").first(),
          ).toBeVisible();
          await expect(page.getByText(/accrued/i)).toHaveCount(0);
        });
        if (width === 390) return;
        await page.getByRole("button", { name: /^Ignore Form 1095-C/ }).click();
        const menu = page.getByRole("menu", { name: "Ignore" });
        await menu.getByRole("textbox").fill("No 1095-C this year.");
        await menu.getByRole("menuitem", { name: "Already sent another way" }).click();
        await journey.step("J12 step 4: the 1095-C ignored, with Undo (POR-03f)", async () => {
          const row = page.locator("[data-request]", {
            hasText: "Form 1095-C From Mercer Hill Health",
          });
          await expect(row.getByRole("button", { name: "Undo" })).toBeVisible();
        });
      },
    );

    test(
      `J12 5: Claire opens the 1095-C request, reads why, and comments (POR-04a)${at}`,
      owner("R-01 · R-01-T21 Playwright (POR-04) · S10, Fri Mar 19, 2027"),
      async ({ journey }) => {
        test.fixme(journey.project !== "fixture", "the portal sign-in BFF is P-08-T10's (S6)");
        await journey.page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
        await journey.as("claire-feld", "/documents", { clock: DEMO_INSTANT });
        const page = journey.page;
        await page
          .getByRole("button", { name: "Form 1095-C From Mercer Hill Health" })
          .first()
          .click();
        const sheet = page.getByRole("dialog");
        await journey.step(
          "J12 step 5: the 1095-C sheet (POR-04a)",
          async () => {
            await expect(sheet.getByText("Why we need it")).toBeVisible();
            await expect(sheet.getByText("To do · requested Feb 3")).toBeVisible();
            await expect(sheet.getByText(/accrued/i)).toHaveCount(0);
          },
          { include: "[role='dialog']" },
        );
        const composer = sheet.getByPlaceholder("Write a comment…");
        await composer.fill("I'll download it tonight.");
        await composer.press("Enter");
        await journey.step(
          "J12 step 5: the comment joins the shared thread",
          async () => {
            await expect(sheet.getByText("I'll download it tonight.")).toBeVisible();
          },
          { include: "[role='dialog']" },
        );
      },
    );

    test(
      `J12 15: Sam Ortiz sees only Keystone's nine requests in his room (POR-14a)${at}`,
      owner("R-01 · R-01-T21 Playwright (POR-14) · S10, Fri Mar 19, 2027"),
      async ({ journey }) => {
        test.fixme(journey.project !== "fixture", "the portal sign-in BFF is P-08-T10's (S6)");
        await journey.page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
        await journey.as("sam-ortiz", "/requests", { clock: DEMO_INSTANT });
        const page = journey.page;
        await journey.step(
          "J12 step 15: Sam's room, 4 of 9 (POR-14a)",
          async () => {
            await expect(page.getByText("4 of 9 uploaded").first()).toBeVisible();
            await expect(page.getByText("Sam Ortiz · Keystone").first()).toBeVisible();
            await expect(page.getByText(/accrued/i)).toHaveCount(0);
          },
          // INV-4: the third party never sees the client's own documents or home.
          { outOfScope: ["Form 1095-C From Mercer Hill Health", "Upload 2 documents"] },
        );
      },
    );
  }
});
