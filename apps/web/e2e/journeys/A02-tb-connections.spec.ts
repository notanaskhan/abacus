// A-02's journey steps (A-02-T34; A-02 §2 "Journeys advanced"; blueprint §7): j04 2 Granite Peak's
// FY2026 TB on AUD-06, j02 6 Tess Moreno connects QuickBooks Online and the Front Range Bank feed
// on POR-16 (e → b → c → a), j03 7 Northwind's TB agreed with its three ties, and POR-16's
// reconnect. In the fixture project each step opens its screen's own artboard (the screen's
// scenario and persona, `/components/screens/<ID>?st=<state>`); axe and INV-1 to INV-5 run after
// every step. The full-stack and hosted runs wait for A-02's live swaps on staging and are
// `test.fixme` naming their owner (journey-e2e skill), never skipped or left out. The portal is
// white-labelled: no POR-16 step may show the product's name (INV-4).
import { expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const LIVE_OWNER =
  "A-02-T24 and A-02-T28 live on staging (AUD-06, POR-16), A-02 §10; staging walk by M8, Fri May 28, 2027";

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

function artboard(id: string, state: string): string {
  return `/components/screens/${id}?st=${state}`;
}

test.describe("A-02 journeys: the trial balance and the client's connections", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
    test.fixme(journey.project !== "fixture", LIVE_OWNER);
  });

  test("j04 2: Granite Peak's FY2026 TB on AUD-06", owner(LIVE_OWNER), async ({ journey }) => {
    await journey.as("hannah-leclerc", artboard("AUD-06", "empty"));
    await journey.step("j04 step 2: Granite Peak has no TB yet (AUD-06 empty)", async (page) => {
      await expect(page.locator("[data-artboard]").first()).toBeVisible();
    });
    await journey.as("hannah-leclerc", artboard("AUD-06", "h"));
    await journey.step(
      "j04 step 2: Granite Peak's FY2026 TB, Final layer (AUD-06 h)",
      async (page) => {
        await expect(page.getByText(/Granite Peak/).first()).toBeVisible();
      },
    );
  });

  test(
    "j02 6: Tess connects QuickBooks Online and the bank feed",
    owner(LIVE_OWNER),
    async ({ journey }) => {
      for (const [state, label] of [
        ["e", "the first QuickBooks Online connect, read-only (POR-16 e)"],
        ["b", "the consent sheet, Continue disabled until authorised (POR-16 b)"],
        ["c", "a connection Connecting… (POR-16 c)"],
        ["a", "QuickBooks Online and Front Range Bank connected (POR-16 a)"],
      ] as const) {
        await journey.as("tess-moreno", artboard("POR-16", state));
        await journey.step(`j02 step 6: ${label}`, async (page) => {
          const shown = page.locator("[data-artboard]").first();
          await expect(shown).toBeVisible();
          await expect(shown.getByText(/Accrued/)).toHaveCount(0);
        });
      }
    },
  );

  test("j03 7: Northwind's TB agreed with three ties", owner(LIVE_OWNER), async ({ journey }) => {
    await journey.as("hannah-leclerc", artboard("AUD-06", "a"));
    await journey.step(
      "j03 step 7: Northwind PY2025 v1 with its ties (AUD-06 a)",
      async (page) => {
        await expect(page.getByText(/Northwind/).first()).toBeVisible();
      },
    );
    await journey.as("hannah-leclerc", artboard("AUD-06", "c"));
    await journey.step("j03 step 7: a tie off by 1,560.00 is flagged (AUD-06 c)", async (page) => {
      await expect(page.getByText(/1,560\.00/).first()).toBeVisible();
    });
  });

  test(
    "por16 reconnect: a lapsed connection asks the client to reconnect",
    owner(LIVE_OWNER),
    async ({ journey }) => {
      for (const [state, label] of [
        ["b", "Reconnect American Express: the consent sheet (POR-16 b)"],
        ["c", "the Amex card Connecting… (POR-16 c)"],
        ["d", "reconnected by Tess Moreno (POR-16 d)"],
      ] as const) {
        await journey.as("tess-moreno", artboard("POR-16", state));
        await journey.step(`por16: ${label}`, async (page) => {
          const shown = page.locator("[data-artboard]").first();
          await expect(shown).toBeVisible();
          await expect(shown.getByText(/Accrued/)).toHaveCount(0);
        });
      }
    },
  );
});
