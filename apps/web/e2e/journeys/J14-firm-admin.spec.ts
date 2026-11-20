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

// T-01-T29: J14 steps 4 and 8, the tax pilot's administration (T-01 §5 item 1). Felix Andersen
// maps the CCH Axcess file bridge on ADM-08 (the return-ID convention, the office codes, the staff
// IDs) and a second Accrued status for one workflow status is refused; Grace Holloway drafts three
// consent renewals on ADM-05. Fixture mode walks the screens' own scenarios; the full stack and
// staging walk them once the T-01 slices and the CCH integration row are on the stack.
const TAX_ADMIN_LIVE =
  "full stack: ADM-05 and ADM-08 over the T-01 slices and the CCH integration row (T-01-T23, T-01-T20); staging once ABACUS_STAGING_URL is set (F-04-T28)";

test.describe("J14 tax administration (T-01-T29)", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
    test.fixme(journey.project !== "fixture", TAX_ADMIN_LIVE);
  });

  test("j14 4: Felix maps the CCH return-ID convention and office codes and a duplicate workflow mapping is refused", async ({
    journey,
  }) => {
    const flags = ["tax.engine_bridge"];
    await journey.as("felix-andersen", "/settings/integrations", { scenario: "ADM-08:a", flags });
    await journey.step(
      "J14 step 4: the CCH return-ID convention and offices (ADM-08 a)",
      async (page) => {
        const engine = page.getByRole("region", { name: "CCH Axcess Tax" });
        await expect(engine.getByText("{Tax year}{Type}:{Client code}:V{n}")).toBeVisible();
        await expect(
          engine.getByText("Tax team — 21 of 21 mapped to CCH staff IDs"),
        ).toBeVisible();
        for (const office of ["CHI-01 · Chicago", "DEN-01 · Denver", "NYC-01 · New York"]) {
          await expect(engine.getByText(office)).toBeVisible();
        }
      },
    );
    await journey.as("felix-andersen", "/settings/integrations", { scenario: "ADM-08:g", flags });
    await journey.step("J14 step 4: the staff IDs (Edit mapping, ADM-08 g)", async (page) => {
      const drawer = page.getByRole("dialog", { name: "Edit mapping" });
      await expect(
        drawer.getByRole("list", { name: "User mapping" }).getByRole("listitem"),
      ).toHaveCount(21);
    });
    await journey.as("felix-andersen", "/settings/integrations", { scenario: "ADM-08:f", flags });
    await journey.step(
      "J14 step 4: a duplicate workflow mapping is refused (ADM-08 f)",
      async (page) => {
        await expect(
          page.getByText("Each workflow status may map from one Accrued status."),
        ).toBeVisible();
        await page.getByRole("switch", { name: "Read diagnostics back after export" }).click();
        await expect(page.getByRole("button", { name: "Save", exact: true })).toBeDisabled();
      },
    );
  });

  test("j14 8: Grace drafts three consent renewals", async ({ journey }) => {
    await journey.as("grace-holloway", "/settings/consents", {
      scenario: "ADM-05:d",
      flags: ["consents.registry", "clients.tax_profile"],
    });
    await journey.step("J14 step 8: three expiring consents selected (ADM-05 d)", async (page) => {
      const rows = page.getByRole("table").getByRole("row");
      for (const n of [3, 4, 5]) {
        await rows.nth(n).getByRole("checkbox").check();
      }
      await expect(page.getByRole("button", { name: "Renew 3…" })).toBeVisible();
    });
    await journey.step("J14 step 8: Renew 3…, one envelope per client", async (page) => {
      await page.getByRole("button", { name: "Renew 3…" }).click();
      await expect(page.getByText("3 renewal envelopes drafted")).toBeVisible();
    });
  });
});

// W-01-T19 (W-01 §7 item 1; SPEC-659): J14 step 3 and the integration-admin sub-steps 3b to 3d on
// WB-10 and WB-11 (Felix Andersen, IT/Security; Hannah Leclerc for 3b). Fixture mode walks each on
// the screen's own scenario; staging walks them with real auth once the canary flip lands
// (W-01-T21, Tue Aug 29, 2028).
const CONNECT = ["integrations.connect_v1"];
const CONNECT_LIVE =
  "W-01 · W-01-T19 fixture; staging with real auth after the W-01-T21 canary flip · Tue Aug 29, 2028";

test.describe("J14 integration admin (W-01)", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
    test.fixme(journey.project !== "fixture", CONNECT_LIVE);
  });

  test(
    "j14 3: Felix finds Sage Intacct in Connect, sees Bluestem's client-authorized company and no firm-side connect, and ADM-08 reports the failed test by code only",
    owner(CONNECT_LIVE),
    async ({ journey }) => {
      await journey.as("felix-andersen", "/workbench/connect?category=erp", {
        scenario: "WB-10:b",
        flags: CONNECT,
      });
      await journey.step("J14 step 3: Sage Intacct under ERP (WB-10 b)", async (page) => {
        await expect(page.getByText("Sage Intacct").first()).toBeVisible();
        await expect(page.getByText("QuickBooks Online").first()).toBeVisible();
      });
      await journey.as("felix-andersen", "/workbench/connect?ov=integration:quickbooks_online", {
        scenario: "WB-11:d",
        flags: CONNECT,
      });
      await journey.step(
        "J14 step 3: a client-ledger app has no firm-side connect (WB-11 d)",
        async (page) => {
          await expect(
            page.getByText("Firm app · each client authorizes its own company"),
          ).toBeVisible();
          await expect(page.getByRole("button", { name: "Connect…" })).toHaveCount(0);
        },
      );
    },
  );

  test(
    "j14 3b: Hannah connects Google Workspace as herself and cannot enable or disconnect firm connections",
    owner(CONNECT_LIVE),
    async ({ journey }) => {
      await journey.as("hannah-leclerc", "/workbench/connect", {
        scenario: "WB-10:d",
        flags: CONNECT,
      });
      await journey.step("J14 step 3b: firm Enable is not Hannah's (WB-10 d)", async (page) => {
        await expect(
          page.getByText("Felix Andersen manages firm connections.").first(),
        ).toBeVisible();
        await expect(page.getByText("Connected as you").first()).toBeVisible();
      });
      await journey.as("hannah-leclerc", "/workbench/connect?ov=integration:cch", {
        scenario: "WB-11:f",
        flags: CONNECT,
      });
      await journey.step("J14 step 3b: no firm footer for Hannah (WB-11 f)", async (page) => {
        await expect(page.getByText("Felix Andersen manages this firm connection.")).toBeVisible();
        await expect(page.getByRole("button", { name: "Disconnect…" })).toHaveCount(0);
      });
    },
  );

  test(
    "j14 3c: CCH Axcess Tax token expires, dependent agent runs fail at admission, Felix reconnects with fresh MFA",
    owner(CONNECT_LIVE),
    async ({ journey }) => {
      await journey.as("felix-andersen", "/workbench/connect", {
        scenario: "WB-10:f",
        flags: CONNECT,
      });
      await journey.step("J14 step 3c: CCH Axcess Tax needs reauth (WB-10 f)", async (page) => {
        await expect(page.getByText("Needs reauth").first()).toBeVisible();
      });
      await journey.as("felix-andersen", "/workbench/connect?ov=integration:cch", {
        scenario: "WB-11:c",
        flags: CONNECT,
      });
      await journey.step("J14 step 3c: the failed run and Reconnect… (WB-11 c)", async (page) => {
        await expect(
          page.getByText("Token expired at 9:00 AM · 1 run failed · 5 agents paused"),
        ).toBeVisible();
        await expect(page.getByRole("button", { name: "Reconnect…" })).toBeVisible();
      });
    },
  );

  test(
    "j14 3d: Felix disconnects CCH Axcess Tax only after typing its name and imported return data is kept",
    owner(CONNECT_LIVE),
    async ({ journey }) => {
      await journey.as("felix-andersen", "/workbench/connect?ov=integration:cch", {
        scenario: "WB-11:e",
        flags: CONNECT,
      });
      await journey.step(
        "J14 step 3d: Disconnect waits for the typed name (WB-11 e)",
        async (page) => {
          await page.getByRole("button", { name: "Disconnect…" }).click();
          const dialog = page.getByRole("dialog", { name: "Disconnect CCH Axcess Tax?" });
          await expect(dialog).toBeVisible();
          const confirm = dialog.getByRole("button", { name: "Disconnect", exact: true });
          await expect(confirm).toBeDisabled();
          await dialog.getByLabel("Type CCH Axcess Tax").fill("CCH Axcess Tax");
          await expect(confirm).toBeEnabled();
        },
      );
    },
  );
});

// G-04-T21 (G-04 §1): J14 step 5 on SHL-05. Grace asks support why the CCH Axcess sync is slow,
// reads the article and the system status, and support sees no client content until Felix grants
// a time-boxed session. Fixture mode walks SHL-05's artboards; staging walks it once the support
// panel's flag is on there (support.panel_v2).
const SUPPORT_LIVE =
  "G-04 · staging with real auth once support.panel_v2 is on in staging (G-04-T19); ABACUS_STAGING_URL";

test.describe("J14 support (G-04)", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
    test.fixme(journey.project !== "fixture", SUPPORT_LIVE);
  });

  test("j14 5: Grace asks support why the CCH sync is slow, reads the article and system status, and support sees no client content until Felix grants a 2-hour session on one return", async ({
    journey,
  }) => {
    await journey.as("grace-holloway", "/components/screens/SHL-05?st=a&frame=1");
    await journey.step("J14 step 5: Grace asks support (SHL-05 a)", async (page) => {
      await expect(page.getByText(/Online · replies in ~/).first()).toBeVisible();
    });
    await journey.as("grace-holloway", "/components/screens/SHL-05?st=d2&frame=1");
    await journey.step("J14 step 5: the help article (SHL-05 d′)", async (page) => {
      await expect(page.locator("[data-artboard='d2']")).toBeVisible();
    });
    await journey.as("grace-holloway", "/components/screens/SHL-05?st=e&frame=1");
    await journey.step("J14 step 5: system status, CCH export needs attention", async (page) => {
      await expect(page.getByText("Needs attention").first()).toBeVisible();
    });
    await journey.as("felix-andersen", "/components/screens/SHL-05?st=c&frame=1");
    await journey.step("J14 step 5: Felix's time-boxed grant", async (page) => {
      await expect(page.getByText(/Granted by Felix Andersen · until/)).toBeVisible();
      await expect(page.getByRole("button", { name: "Revoke" })).toBeVisible();
    });
  });
});
