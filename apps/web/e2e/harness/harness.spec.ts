// The harness core in each of its four projects (F-04-T21): a persona's entry step passes axe
// (serious and critical = 0, forced colors too) and INV-1 to INV-5, and the UI layer of
// assertInvariants fails, naming the step, on each kind of page it must reject. F-04-T30 adds the
// data-layer checker and the injected-violation self-tests against real audit events.
import { AGENT_APPROVER, DEMO_INSTANT, PERSONAS, assertInvariants, expect, test } from "./index";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};

test("harness: Hannah Leclerc's entry step passes axe and INV-1 to INV-5", async ({ journey }) => {
  const hosted = journey.project === "staging" || journey.project === "canary";
  // Hosted projects run only from the nightly and release jobs, which set their URL (F-04-T28).
  test.skip(
    hosted && HOSTED_URL[journey.project] === undefined,
    `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
  );
  await journey.as("hannah-leclerc", "/", { clock: DEMO_INSTANT });
  await journey.step("harness: Home as Hannah Leclerc", async (page) => {
    await expect(page.getByRole("navigation").first()).toBeVisible();
  });
});

test.describe("assertInvariants rejects what it must (UI layer)", () => {
  const hannah = PERSONAS["hannah-leclerc"];

  async function rejects(
    page: import("@playwright/test").Page,
    html: string,
    inv: RegExp,
    ctx: Partial<Parameters<typeof assertInvariants>[1]> = {},
  ): Promise<void> {
    await page.setContent(`<!doctype html><html lang="en"><body>${html}</body></html>`);
    const step = "self-check step";
    await expect(assertInvariants(page, { step, persona: hannah, ...ctx })).rejects.toThrow(inv);
    await expect(assertInvariants(page, { step, persona: hannah, ...ctx })).rejects.toThrow(
      /self-check step/,
    );
  }

  test("a clean page holds", async ({ page }) => {
    await page.setContent(
      '<!doctype html><html lang="en"><body><p>Hannah Leclerc via Agent</p><button data-human-verb="Approve">Approve</button></body></html>',
    );
    await assertInvariants(page, { step: "clean", persona: hannah });
  });

  test("INV-1: a human verb on an agent-owned element", async ({ page }) => {
    await rejects(page, '<div data-actor="agent"><button>Approve</button></div>', /INV-1/);
  });

  test("INV-2: an agent-set value with neither a verified citation nor Uncited", async ({
    page,
  }) => {
    await rejects(
      page,
      '<ul><li><span data-actor="agent" data-filled="suggested">$48,600</span></li></ul>',
      /INV-2/,
    );
  });

  test("INV-2: an Uncited value whose human gate is enabled", async ({ page }) => {
    await rejects(
      page,
      '<ul><li><span data-actor="agent" data-filled="suggested">$48,600</span> Uncited <button data-human-verb="Accept">Accept</button></li></ul>',
      /INV-2/,
    );
  });

  test("INV-3: a walled client on Lena Park's page, and a hidden count", async ({ page }) => {
    await rejects(page, "<p>Ashford Manufacturing Co.</p>", /INV-3/, {
      persona: PERSONAS["lena-park"],
    });
    await rejects(page, "<p>Showing 26 of 27 · 1 hidden</p>", /INV-3/);
  });

  test("INV-4: a portal persona sees another client, or the word Accrued", async ({ page }) => {
    await rejects(page, "<p>Granite Peak Outdoor Supply, Inc.</p>", /INV-4/, {
      persona: PERSONAS["claire-feld"],
      outOfScope: ["Granite Peak Outdoor Supply, Inc."],
    });
    await rejects(page, "<footer>Powered by Accrued</footer>", /INV-4/, {
      persona: PERSONAS["claire-feld"],
    });
  });

  test("INV-5: the Agent as approver", async ({ page }) => {
    expect(AGENT_APPROVER.test("Approved by Accrued Agent")).toBe(true);
    await rejects(page, "<p>Approved by Accrued Agent · Sep 14</p>", /INV-5/);
  });
});
