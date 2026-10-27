// J14 firm administration (G-01-T16; G-01 §10 item 1; blueprint §7): Grace Holloway adds Lena Park
// as a seasonal preparer, walls her from Ashford Manufacturing Co., Margaret Okonkwo approves, a
// wall on the client's own relationship partner is refused, and the wall log names both people;
// then, as Lena, the walled client is gone (INV-3). Each step runs on the harness (axe and INV-1 to
// INV-5 after it). In fixture mode a step opens the real route on the screen's own scenario
// (`?screen=&st=`, DEC-457); the full stack walks them once the nightly loads the people slice,
// and staging and the canary after the batch deploy (G-01-T19). `firm_settings.v2` is retired
// (G-01-T17, DEC-594).
import { DEMO_INSTANT, expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const WALLED = "Ashford Manufacturing Co."; // ADM-03's wall for Lena Park (INV-3)
// ADM-07 (G-02-T13) sits behind this flag, which E0 leaves off (G-02-T21).
const AUDIT_LOG = ["audit_log.explorer"];
// ADM-03b and f (fixtures/scenarios/ADM-03.ts CLOCK_920): 9:20 AM, when Grace adds the wall.
const AT_920 = "2026-09-14T09:20:00-05:00";
const LIVE_LATER =
  "G-01 · G-01-T16 fixture; full stack after G-01-T17, staging and canary G-01-T19 · Fri Apr 30, 2027";

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("J14 firm administration", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
    // The staging smoke is written and waits for the batch deploy (G-01-T19).
    test.fixme(journey.project !== "fixture", "the people slice is not in E0");
  });

  test(
    "j14 1: Grace adds seasonal preparer Lena Park (Denver, offshore off)",
    owner(LIVE_LATER),
    async ({ journey }) => {
      await journey.as("grace-holloway", "/settings/people?screen=ADM-02&st=d", {
        clock: DEMO_INSTANT,
      });
      await journey.step("J14 step 1: Lena Park's access as Grace Holloway", async (page) => {
        const lena = page.getByRole("dialog", { name: "Lena Park" });
        await expect(lena).toBeVisible();
        await expect(lena.getByText("Denver").first()).toBeVisible();
        await expect(lena.getByText("Oct 31, 2026").first()).toBeVisible(); // the seasonal end
      });
      await journey.as("grace-holloway", "/settings/offices?screen=ADM-03&st=a", {
        clock: DEMO_INSTANT,
      });
      await journey.step("J14 step 1: the offshore group stays empty", async (page) => {
        await expect(page.getByText("0 members").first()).toBeVisible();
      });
    },
  );

  test(
    "j14 2: Grace walls Lena Park from Ashford, Margaret approves, Neil Ashcroft is refused, and the wall log names both",
    owner(LIVE_LATER),
    async ({ journey }) => {
      await journey.as("grace-holloway", "/settings/offices?screen=ADM-03&st=b", {
        clock: AT_920,
      });
      await journey.step("J14 step 2: the new wall on Lena Park and Ashford", async (page) => {
        const sheet = page.getByRole("dialog", { name: "New ethical wall" });
        await expect(sheet).toBeVisible();
        await expect(sheet.getByRole("button", { name: "Person: Lena Park" })).toBeVisible();
        await expect(sheet.getByText("Block agent runs she starts on this client")).toBeVisible();
      });
      await journey.as("grace-holloway", "/settings/offices?screen=ADM-03&st=c", {
        clock: DEMO_INSTANT,
      });
      await journey.step(
        "J14 step 2: Neil Ashcroft can't be walled from his own client",
        async (page) => {
          const sheet = page.getByRole("dialog", { name: "New ethical wall" });
          await expect(
            sheet.getByText(
              "Neil Ashcroft leads this relationship. Reassign the relationship partner first.",
            ),
          ).toBeVisible();
        },
      );
      await journey.as("grace-holloway", "/settings/offices?screen=ADM-03&st=g", {
        clock: DEMO_INSTANT,
      });
      await journey.step("J14 step 2: the wall log names Grace and Margaret", async (page) => {
        const log = page.getByRole("dialog", { name: "Ethical wall" });
        await expect(log.getByText("Ethical wall added by Grace Holloway")).toBeVisible();
        await expect(log.getByText("Approved by Margaret Okonkwo")).toBeVisible();
      });
    },
  );

  test("j14 2b: as Lena, CLI-01 hides Ashford (INV-3)", owner(LIVE_LATER), async ({ journey }) => {
    await journey.as("lena-park", "/clients", { clock: DEMO_INSTANT });
    await journey.step(
      "J14 step 2b: the Clients index as Lena Park",
      async (page) => {
        await expect(page.getByRole("heading", { name: "Clients", exact: true })).toBeVisible();
        await expect(page.getByText(WALLED)).toHaveCount(0);
      },
      { outOfScope: [WALLED] },
    );
  });

  test(
    "j14 7: Felix reviews via-Agent events and exports after fresh MFA",
    owner(
      "G-02 · G-02-T21 fixture; full stack once E0 turns audit_log.explorer on, staging and the canary after the batch deploy · M7, Fri Apr 16, 2027",
    ),
    async ({ journey }) => {
      await journey.as("felix-andersen", "/settings/audit-log?screen=ADM-07&st=b", {
        clock: DEMO_INSTANT,
        flags: AUDIT_LOG,
      });
      await journey.step("J14 step 7: the via Agent events as Felix Andersen", async (page) => {
        const feed = page.getByRole("list", { name: "Audit log" });
        await expect(feed.getByRole("listitem")).toHaveCount(4);
        await expect(page.getByText("Showing 4 of 1,962")).toBeVisible();
        // INV-5: the agent acts for a named person, never as an actor of its own.
        await expect(page.getByText("Accrued Agent")).toHaveCount(0);
      });
      await journey.as("felix-andersen", "/settings/audit-log?screen=ADM-07&st=e", {
        clock: DEMO_INSTANT,
        flags: AUDIT_LOG,
      });
      await journey.step(
        "J14 step 7: Export… with values, and the ready manifest",
        async (page) => {
          await page.getByRole("button", { name: /Export…/ }).click();
          const dialog = page.getByRole("dialog");
          await expect(dialog.getByText("CSV + signed JSON manifest")).toBeVisible();
          await expect(
            dialog.getByRole("switch", { name: "Include before/after values" }),
          ).toBeVisible();
          await dialog.getByRole("button", { name: "Export", exact: true }).click();
          await expect(page.getByText("Export ready · SHA-256 manifest included")).toBeVisible();
        },
      );
    },
  );
});
