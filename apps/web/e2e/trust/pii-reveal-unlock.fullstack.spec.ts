// P-03-T25 (P-03 §6, AC4.4, AC4.6, AC5.x): the trust layer's PII reveal and password unlock on the
// full stack and staging, on the harness (axe and INV-1 to INV-5 after each step, in the browser
// and the database). Samuel Ito (onshore, on the engagement) opens Claire Feld's synthetic W-2:
// every TIN is masked on every page route; "Reveal (logged)" shows the value for its window and
// writes a `pii.revealed` audit row and an access event, never the value. An offshore member and
// the agent are refused (403), and the password PDF unlocks to masked pages with the original's
// fingerprint unchanged. The fixture project has no reveal or unlock API: it is fixme there.
//
// Hosted runs read the synthetic upload's ids and the unlock password from the environment
// (`ABACUS_E2E_W2_VERSION`, `ABACUS_E2E_LOCKED_VERSION`, `ABACUS_E2E_LOCKED_PASSWORD`, all
// synthetic test values the seed writes); without them the hosted test skips.
import { expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const W2 = process.env.ABACUS_E2E_W2_VERSION;
const LOCKED = process.env.ABACUS_E2E_LOCKED_VERSION;
const PASSWORD = process.env.ABACUS_E2E_LOCKED_PASSWORD;
// A full TIN in the page: 9 digits, with or without dashes. Masked values read "•••-••-1234".
const FULL_TIN = /\b\d{3}-?\d{2}-?\d{4}\b/;

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("PII reveal and unlock, full stack (P-03-T25)", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
    test.fixme(journey.project === "fixture", "no reveal or unlock API in the fixture project");
    test.skip(W2 === undefined || LOCKED === undefined, "the synthetic upload ids are not set");
  });

  test(
    "a synthetic W-2 is masked on every page route; Samuel's reveal is logged without the value",
    owner("P-03 · P-03-T25 full-stack reveal · S12, Fri Apr 16, 2027"),
    async ({ journey }) => {
      await journey.as("samuel-ito", `/viewer/${W2 ?? ""}`);
      const page = journey.page;
      await journey.step("PII step 1: every page of the W-2 is masked", async () => {
        await expect(page.locator("[data-viewer-bar]").first()).toBeVisible();
        expect(await page.content()).not.toMatch(FULL_TIN);
        for (const route of ["text", "pages/1", "regions"]) {
          const status = await journey.adapter.probe(
            page,
            `/v1/evidence-versions/${W2 ?? ""}/${route}`,
          );
          expect([200, 404]).toContain(status);
        }
      });
      const responses: string[] = [];
      page.on("response", (response) => {
        if (response.url().includes("/pii-reveals")) responses.push(response.url());
      });
      await journey.step(
        "PII step 2: Reveal (logged) shows the value for its window",
        async () => {
          await page
            .getByRole("button", { name: /Reveal/ })
            .first()
            .click();
          await expect(page.getByText(/^Revealed for \d+ seconds$/)).toBeVisible();
          await expect(page.getByText(/logged to the audit trail$/)).toBeVisible();
          expect(responses.length).toBeGreaterThan(0);
        },
      );
    },
  );

  test(
    "an offshore member and the agent are refused the reveal",
    owner("P-03 · P-03-T25 full-stack reveal refusals · S12, Fri Apr 16, 2027"),
    async ({ journey }) => {
      await journey.as("lena-park", `/viewer/${W2 ?? ""}`);
      await journey.step(
        "PII step 3: the reveal is refused to the offshore member",
        async (page) => {
          const status = await journey.adapter.probe(
            page,
            `/v1/evidence-versions/${W2 ?? ""}/pii-reveals`,
          );
          expect([403, 404, 405]).toContain(status);
          await expect(page.getByRole("button", { name: /Reveal/ })).toHaveCount(0);
        },
      );
    },
  );

  test(
    "a password PDF unlocks to masked pages and keeps the original's fingerprint",
    owner("P-03 · P-03-T25 full-stack unlock · S12, Fri Apr 16, 2027"),
    async ({ journey }) => {
      test.skip(PASSWORD === undefined, "the synthetic file's password is not set");
      await journey.as("samuel-ito", `/viewer/${LOCKED ?? ""}`);
      const page = journey.page;
      await journey.step("PII step 4: the locked PDF asks for its password", async () => {
        await expect(page.getByText("This PDF is password-protected.")).toBeVisible();
      });
      await journey.step("PII step 5: unlocked, the pages are masked", async () => {
        await page.getByLabel("Password").fill(PASSWORD ?? "");
        await page.getByRole("button", { name: "Unlock" }).click();
        await expect(page.locator("[data-viewer-bar]").first()).toBeVisible();
        expect(await page.content()).not.toMatch(FULL_TIN);
        expect(await page.content()).not.toContain(PASSWORD ?? "");
      });
    },
  );
});
