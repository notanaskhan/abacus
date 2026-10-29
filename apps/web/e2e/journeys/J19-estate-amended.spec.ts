// J19-estate-amended, P-07's steps (P-07-T62; P-07 §10 DoD 1, blueprint §7.19): the trigger (step
// 0: Grace adds the Estate of Walter Thornbury under the existing Walter Thornbury client, Tue Sep
// 8, 2026, with a conflict check and a person's screening record, then "Create & start
// acceptance"), step 2 (Daniel Reyes, the engagement partner, accepts with conditions in CLI-07: a
// person's decision, INV-1) and step 3 (the estate engagement, Prospect, holds the Form 706, Form
// 1041 and final Form 1040 work items the intake created). Steps 1 and 4 to 8 are other epics'
// (POR-18 R-03; ENG-04, SIG-02, TXT-04, TAX-* T-04): they stay fixme with their owners. Every
// step runs axe and INV-1 to INV-5; nothing on a page reads that the Agent decided (INV-5).
//
// The fixture project walks the real routes on the screens' own scenarios (`?screen=`, DEC-457):
// CLI-06 b to Create, CLI-07 a to the decision, ENG-02's prospect record. Full stack and staging
// walk once `clients.v2`, `engagements.v2` and `engagements.acceptance_v2` are on in the demo firm
// and the demo seed carries the Thornbury holdout (E0 leaves them off; STAGING_JOURNEYS is off).
import { expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const LIVE =
  "clients.v2, engagements.v2 and engagements.acceptance_v2 are off in E0 and the demo seed holds no Thornbury holdout; full stack and staging walk J19 0, 2 and 3 once the demo firm has them (P-07 flag plan, STAGING_JOURNEYS)";
const ACCEPTANCE = "/clients/_clientId_/acceptance/_engagementId_";
const RECORD = "/engagements/_engagementId_";

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("J19-estate-amended (P-07's steps 0, 2 and 3)", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
    test.fixme(journey.project !== "fixture", LIVE);
  });

  test("j19 0: Grace adds the estate under Walter Thornbury with a conflict check", async ({
    journey,
  }) => {
    await journey.as("grace-holloway", "/clients/new", { scenario: "CLI-06:b" });
    await journey.step(
      "J19 0 · CLI-06 b: the dedupe card recommends the existing client",
      async (page) => {
        await expect(page.getByText("96% match · Walter Thornbury").first()).toBeVisible();
        await expect(
          page.getByRole("radio", { name: "Add the estate under this client (recommended)" }),
        ).toHaveAttribute("aria-checked", "true");
      },
    );
    await journey.step(
      "J19 0 · CLI-06 c–e: decedent, executor and the three returns",
      async (page) => {
        const next = page.getByRole("button", { name: "Next" });
        await next.click();
        await expect(
          page.getByText("Walter Thornbury (decedent) → Estate of Walter Thornbury · Decedent"),
        ).toBeVisible();
        await next.click();
        await expect(page.getByRole("textbox", { name: "Name" })).toHaveValue("Paul Thornbury");
        await next.click();
        for (const form of ["Form 706", "Estate Form 1041", "Final Form 1040"]) {
          await expect(page.getByRole("checkbox", { name: form })).toHaveAttribute(
            "aria-checked",
            "true",
          );
        }
      },
    );
    await journey.step(
      "J19 0 · CLI-06 a: no conflicts; Grace records the OFAC search",
      async (page) => {
        await page.getByRole("button", { name: "Next" }).click();
        await expect(page.getByText("No conflicts").first()).toBeVisible();
        await expect(page.getByText("Same family · not adverse").first()).toBeVisible();
        await page.getByRole("button", { name: "Record…" }).first().click();
        await page.getByRole("menuitem", { name: "No match" }).click();
        await expect(page.getByText("No match · Recorded by Grace Holloway")).toBeVisible();
      },
    );
    await journey.step(
      "J19 0 · CLI-06 f: Create & start acceptance opens CLI-07",
      async (page) => {
        await page.getByRole("button", { name: "Next" }).click();
        await expect(page.getByText("Estate of Walter Thornbury").first()).toBeVisible();
        await page.getByRole("button", { name: "Create & start acceptance" }).click();
        await expect(page).toHaveURL(/\/clients\/[^/]+\/acceptance\/[^/?]+/);
      },
    );
  });

  test.fixme(
    "j19 1: Paul Thornbury answers the new-engagement intake (POR-18)",
    owner("R-03 · POR-18 prospect intake (intake-only portal scope until G3)"),
    async () => {},
  );

  test("j19 2: Daniel accepts Thornbury with conditions", async ({ journey }) => {
    await journey.as("daniel-reyes", ACCEPTANCE, { scenario: "CLI-07:a" });
    await journey.step("J19 2 · CLI-07 a: three flags await the partner", async (page) => {
      await expect(page.getByText("Form 706 is required").first()).toBeVisible();
    });
    await journey.step(
      "J19 2 · CLI-07: a flag becomes a condition; Daniel decides",
      async (page) => {
        await page
          .getByRole("button", { name: /Make this a condition/ })
          .first()
          .click();
        await expect(page.getByRole("textbox", { name: "Condition 1" })).toHaveValue(
          "Form 706 is required",
        );
        await page
          .getByRole("textbox", { name: "Rationale" })
          .fill("Every flag can be resolved by a condition.");
        await page.locator("[data-dock-footer] button").click();
        await expect(page.locator("[data-dock-decided]")).toContainText(
          "Accepted with conditions",
        );
      },
    );
  });

  test("j19 3: the estate engagement holds the 706, 1041 and final 1040 work items", async ({
    journey,
  }) => {
    await journey.as("daniel-reyes", RECORD, {
      scenario: "ENG-02:prospect",
    });
    await journey.step("J19 3 · ENG-02: the estate engagement, Prospect", async (page) => {
      await expect(page.getByRole("heading", { name: /Estate returns/ })).toBeVisible();
      await expect(page.getByText("Acceptance pending — Daniel Reyes").first()).toBeVisible();
    });
    await journey.step("J19 3 · ENG-02 Work items: Form 706, 1041 and 1040", async (page) => {
      await page.getByRole("tab", { name: /Work items/ }).click();
      for (const name of ["Form 706", "Form 1041", "Form 1040"]) {
        await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
      }
    });
  });

  test.fixme(
    "j19 3b: the engagement letter goes to Paul Thornbury for signature (ENG-04, SIG-02)",
    owner("N-02 · ENG-04 letter composer and SIG-02 envelopes (G3)"),
    async () => {},
  );

  test.fixme(
    "j19 4–8: Form 706 workpapers, partner approval, the Okafor 1040-X",
    owner("T-04 · TXT-04, TAX-12, TAX-07, TAX-16 (J19's tax steps)"),
    async () => {},
  );
});
