// A-02's journey steps (A-02-T34; A-02 §2 "Journeys advanced"; blueprint §7): j04 2 Granite Peak's
// FY2026 TB on AUD-06, j02 6 Tess Moreno connects QuickBooks Online and the Front Range Bank feed
// on POR-16 (e → b → c → a), j03 7 Northwind's TB agreed with its three ties, and POR-16's
// reconnect. In the fixture project each step opens its screen's own artboard (the screen's
// scenario and persona, `/components/screens/<ID>?st=<state>`); axe and INV-1 to INV-5 run after
// every step. The full-stack and hosted runs wait for A-02's live swaps on staging and are
// `test.fixme` naming their owner (journey-e2e skill), never skipped or left out. The portal is
// white-labelled: no POR-16 step may show the product's name (INV-4).
import type { Page } from "@playwright/test";
import { type Journey, expect, test } from "../harness";

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

// POR-16 is the portal's: Tess opens the real /connections route on the state's own scenario and
// clock (the portal entry's `?screen=POR-16`), not the firm's gallery.
const POR16_CLOCK = {
  a: "2026-09-14T09:24:00-05:00",
  b: "2026-09-14T09:24:00-05:00",
  c: "2026-09-14T09:30:00-05:00",
  d: "2026-09-14T09:31:00-05:00",
  e: "2026-03-04T09:24:00-06:00",
} as const;

async function portal(journey: Journey, state: keyof typeof POR16_CLOCK): Promise<void> {
  await journey.as("tess-moreno", "/connections", {
    scenario: `POR-16:${state}`,
    clock: POR16_CLOCK[state],
  });
}

/** INV-4: the portal never shows the product's name, a posting scope or a password field. */
async function whiteLabelled(page: Page): Promise<void> {
  await expect(page.getByText(/Accrued|post (?:approved )?entries/i)).toHaveCount(0);
  await expect(page.locator("input[type='password']")).toHaveCount(0);
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
    // h stands on Mon Nov 9, 2026, 10:15 AM CST, after Granite Peak's FY2026 Final release.
    await journey.as("hannah-leclerc", artboard("AUD-06", "h"), {
      clock: "2026-11-09T10:15:00-06:00",
    });
    await journey.step(
      "j04 step 2: Granite Peak's FY2026 TB, Final layer (AUD-06 h)",
      async (page) => {
        // The TB pane names no client: h is the Final layer, handed off to tax, with Granite
        // Peak's FY2026 balances (seed/aud06.ts).
        await expect(page.getByRole("tab", { name: "Final", selected: true })).toBeVisible();
        await expect(page.getByRole("button", { name: "Hand off to tax…" })).toBeVisible();
        await expect(page.getByText("$11,420,000.00").first()).toBeVisible();
      },
    );
  });

  test(
    "j02 6: Tess connects QuickBooks Online and the bank feed",
    owner(LIVE_OWNER),
    async ({ journey }) => {
      await portal(journey, "e");
      await journey.step(
        "j02 step 6: the first QuickBooks Online connect, read-only (POR-16 e)",
        async (page) => {
          await page
            .getByRole("listitem", { name: "QuickBooks Online" })
            .getByRole("button", { name: "Connect" })
            .click();
          const sheet = page.getByRole("dialog", { name: "Connect QuickBooks Online" });
          await expect(sheet.getByText("Brightwater Hale will read your ledger")).toBeVisible();
          await expect(
            sheet.getByRole("button", { name: "Continue to QuickBooks Online" }),
          ).toBeDisabled();
          await whiteLabelled(page);
        },
      );
      await portal(journey, "b");
      await journey.step(
        "j02 step 6: the consent sheet, Continue disabled until authorised (POR-16 b)",
        async (page) => {
          await page
            .getByRole("listitem", { name: "American Express ••1009" })
            .getByRole("button", { name: "Reconnect" })
            .click();
          const sheet = page.getByRole("dialog");
          await expect(sheet.getByRole("switch")).toBeVisible();
          await expect(
            sheet.getByRole("button", { name: "Continue to American Express" }),
          ).toBeDisabled();
          await whiteLabelled(page);
        },
      );
      await portal(journey, "c");
      await journey.step("j02 step 6: a connection Connecting… (POR-16 c)", async (page) => {
        await expect(page.getByText("Connecting…").first()).toBeVisible();
        await whiteLabelled(page);
      });
      await portal(journey, "a");
      await journey.step(
        "j02 step 6: QuickBooks Online and Front Range Bank connected (POR-16 a)",
        async (page) => {
          await expect(
            page
              .getByRole("listitem", { name: "QuickBooks Online" })
              .getByText(/Connected by Tess Moreno/),
          ).toBeVisible();
          await expect(
            page.getByRole("listitem", { name: "Front Range Bank ••4410" }).getByText("Connected"),
          ).toBeVisible();
          await whiteLabelled(page);
        },
      );
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
      await portal(journey, "a");
      await journey.step(
        "por16: American Express has lapsed: Reconnect (POR-16 a)",
        async (page) => {
          await expect(
            page
              .getByRole("listitem", { name: "American Express ••1009" })
              .getByRole("button", { name: "Reconnect" }),
          ).toBeVisible();
          await whiteLabelled(page);
        },
      );
      await portal(journey, "c");
      await journey.step("por16: the Amex card Connecting… (POR-16 c)", async (page) => {
        await expect(
          page.getByRole("listitem", { name: "American Express ••1009" }).getByText("Connecting…"),
        ).toBeVisible();
        await whiteLabelled(page);
      });
      await portal(journey, "d");
      await journey.step("por16: reconnected by Tess Moreno (POR-16 d)", async (page) => {
        await expect(
          page
            .getByRole("listitem", { name: "American Express ••1009" })
            .getByText("reconnected by Tess Moreno · Sep 14, 9:31 AM"),
        ).toBeVisible();
        await whiteLabelled(page);
      });
    },
  );
});
