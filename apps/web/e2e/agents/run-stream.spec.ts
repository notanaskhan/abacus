// P-10-T50 (TASK-7421; SPEC-647 §3.8 AC-T1 to AC-T4, AC-W4; P-10 §10): the run stream in the
// browser. The dock moves over SSE without a refresh, falls back to polling when the stream fails,
// and a session that read a client the viewer may not open is locked; j23 1-run: Margaret Okonkwo
// sees Northwind #4127 blocked on her materiality decision. Each step runs axe and INV-1 to INV-5.
//
// The fixture project walks AUD-02's built artboards (a: #4127 with Risk Assessment Running; d:
// "Waiting on Margaret Okonkwo"). c is the proposed plan, not a running run (docs/screens/AUD-02.md).
// The live halves (SSE delivery, the polling fallback, the locked session) need the full stack: they
// run on the staging project and are skipped where its URL is not set. j11 b2–b3 (Workbench
// screens) stay `test.fixme` until W-02 builds WB-01/02/03 (S40–S45).
import { expect, test } from "../harness";
import { artboard, skipUnhosted } from "../signatures/support";

const W02 = "WB-01/02/03 are W-02's (S40–S45); j11 b2–b3 walk them once built";
const LIVE = "the run stream's live halves need the full stack (staging)";

test.describe("Run stream: the dock (P-10-T50)", () => {
  test("j23 1-run: Northwind #4127 runs, then waits on Margaret Okonkwo's materiality decision", async ({
    journey,
  }) => {
    skipUnhosted(journey.project);
    test.fixme(journey.project !== "fixture", LIVE);
    await journey.as("hannah-leclerc", artboard("AUD-02", "a"));
    await journey.step("j23 1-run: the run is Running in the dock (AUD-02 a)", async (page) => {
      await expect(page.getByText(/Running/).first()).toBeVisible();
    });
    await journey.as("margaret-okonkwo", artboard("AUD-02", "d"));
    await journey.step(
      "j23 1-run: blocked on a partner decision, Margaret Okonkwo (AUD-02 d)",
      async (page) => {
        await expect(page.getByText(/Margaret Okonkwo/).first()).toBeVisible();
        // The agent never decides: no Decide control on an agent-owned surface (INV-1).
        await expect(page.locator("[data-actor='agent'] button")).toHaveCount(0);
      },
    );
  });

  test("the dock moves to Running over SSE without a refresh", async ({ journey }) => {
    skipUnhosted(journey.project);
    test.fixme(journey.project !== "staging" && journey.project !== "canary", LIVE);
    await journey.as("hannah-leclerc", "/audits");
    await journey.step("SSE: the run's state arrives within 2 s of the commit", async (page) => {
      const stream = page.waitForResponse((r) => r.url().includes("/v1/events"), {
        timeout: 10_000,
      });
      await page.getByRole("button", { name: /^Run/ }).first().click();
      await stream;
      await expect(page.getByText(/Dispatched|Running/).first()).toBeVisible({ timeout: 2_000 });
    });
  });

  test("three failed streams fall back to polling and the dock still updates", async ({
    journey,
  }) => {
    skipUnhosted(journey.project);
    test.fixme(journey.project !== "staging" && journey.project !== "canary", LIVE);
    await journey.as("hannah-leclerc", "/audits");
    await journey.step("polling: with /v1/events refused, the run still moves", async (page) => {
      await page.route("**/v1/events*", (route) => route.abort());
      await page.route("**/v1/agent-runs/*/events*", (route) => route.abort());
      await page.getByRole("button", { name: /^Run/ }).first().click();
      await expect(page.getByText(/Dispatched|Running/).first()).toBeVisible({ timeout: 70_000 });
    });
  });

  test("a session that read a client the viewer may not open is locked", async ({ journey }) => {
    skipUnhosted(journey.project);
    test.fixme(journey.project !== "staging" && journey.project !== "canary", W02);
    await journey.as("margaret-okonkwo", "/workbench");
    await journey.step("locked: no figure, no composer (WB-01 g)", async (page) => {
      await expect(page.getByText(/You can’t open this record/).first()).toBeVisible();
      await expect(page.getByRole("textbox", { name: "Message" })).toHaveCount(0);
    });
  });
});

test.describe("J11 b2–b3 on the runtime (W-02)", () => {
  test("j11 b2: the question, the plan and Hannah's approval", async ({ journey }) => {
    test.fixme(true, W02);
    await journey.as("hannah-leclerc", "/workbench");
  });

  test("j11 b3: the workbook and Save to Files, saved 10 s later as Hannah via Agent", async ({
    journey,
  }) => {
    test.fixme(true, W02);
    await journey.as("hannah-leclerc", "/workbench");
  });
});
