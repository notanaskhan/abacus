// J08 partnership 1065 (T-05-T68; T-05 §10 item 1; blueprint §7.8): the P0 core over the
// Ridgeline Property Partners, LP 2025 Form 1065. Olivia runs the Agent tab (TXP-00); Samuel
// reviews Financials (TXP-02), Schedule K (TXP-05), the allocation structure (TXP-06) and the
// capital accounts (TXP-07); the M-2 fix is approved from Issues (TXP-10) and lands in the
// workbook (TXP-11); the memo (TXP-01) is approved and goes stale after the fix; the K-1 package
// (TXP-12, T-02-T32's steps 12 and 16) shares drafts and releases. Every step runs axe and
// INV-1 to INV-5 (journey harness). Steps 3, 4, 8 and 9 (fixed assets, M-1/M-3, basis, states)
// are T-06's screens and stay `test.fixme` naming their owner.
//
// The fixture project walks each step through the real route on its screen's own scenario
// (`?screen=TXP-xx&st=…`, screen-scenarios.ts), with the seed's `tax_entity_returns` and
// `tax_returns` entitlements; `_returnId_` resolves to the Ridgeline return. The full stack and
// staging walk the same routes against the seeded tenant once T-05's slices are on that stack and
// staging's URL is set; until then they are fixme, never skipped.
import { expect, test } from "../harness";
import type { Page } from "@playwright/test";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const LIVE =
  "T-05-T68: full stack once T-05's slices and the fake QBO and CCH are seeded on the stack; staging once ABACUS_STAGING_URL is set (J08 P0 on staging by Fri Jul 7, 2028)";
const K1_OWNER = "T-02-T32: T-02's screens live on staging and the canary, Thu Aug 12, 2027";
const T06 = "T-06: the P1 review sections (TXP-03, TXP-04, TXP-08, TXP-09), S47–S50";
// T-06-T69: both workspaces are the seed's entitlements now; no flag to turn on.
const FLAGS: string[] = [];
const RETURN = "/tax-returns/_returnId_";
const REVIEW = (section: string): string => `${RETURN}/review/${section}`;

function artboard(id: string, state: string): string {
  return `/components/screens/${id}?st=${state}`;
}

/** No control on the page offers a human verb to the agent (INV-1 in words, chapter 04 §6). */
async function noAgentVerb(page: Page): Promise<void> {
  await expect(
    page.getByRole("button", { name: /Agent (approves|signs off|releases|exports)/ }),
  ).toHaveCount(0);
}

test.describe("J08 · P0 core (T-05-T68)", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
    test.fixme(journey.project !== "fixture", LIVE);
  });

  test("j08 1: Olivia runs the Agent tab; Run 1 fails on the expired QBO token, asks the §706(d) question, and Run 2 completes with 11 open items", async ({
    journey,
  }) => {
    await journey.as("olivia-brandt", RETURN, { scenario: "TXP-00:e", flags: FLAGS });
    await journey.step(
      "J08 step 1: Run 1 stopped at Import trial balance (TXP-00 e)",
      async (page) => {
        await expect(page.getByText("Stopped at Import trial balance").first()).toBeVisible();
        await expect(
          page.getByText("QuickBooks Online token expired — reconnect in Workbench › Connect"),
        ).toBeVisible();
        await expect(page.getByRole("button", { name: "Reconnect" })).toBeVisible();
        await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
      },
    );
    await journey.as("olivia-brandt", RETURN, { scenario: "TXP-00:d", flags: FLAGS });
    await journey.step(
      "J08 step 1: the §706(d) question waits on a person (TXP-00 d)",
      async (page) => {
        await expect(page.getByText("Waiting on 1 answer").first()).toBeVisible();
        await expect(
          page.getByText("§706(d) interim closing — Pell Street transfer 6/30/2025"),
        ).toBeVisible();
      },
    );
    await journey.as("olivia-brandt", RETURN, { scenario: "TXP-00:a", flags: FLAGS });
    await journey.step(
      "J08 step 1: Run 2 complete with 11 open items (TXP-00 a)",
      async (page) => {
        await expect(
          page.getByText("10 of 10 steps · 11 open items raised · finished Sep 10, 4:12 PM"),
        ).toBeVisible();
        await noAgentVerb(page);
      },
    );
  });

  test("j08 2: Samuel approves the one mapping judgment and Unmapped reaches 0", async ({
    journey,
  }) => {
    await journey.as("samuel-ito", REVIEW("financials"), { scenario: "TXP-02:e", flags: FLAGS });
    await journey.step(
      "J08 step 2: one account unmapped in the Run 1 snapshot (TXP-02 e)",
      async (page) => {
        await expect(page.getByText("Unmapped", { exact: true }).first()).toBeVisible();
        await expect(page.getByText(/off \(\$158,000\)/).first()).toBeVisible();
      },
    );
    await journey.as("samuel-ito", REVIEW("financials"), { scenario: "TXP-02:a", flags: FLAGS });
    await journey.step("J08 step 2: the TB ties with Unmapped 0 (TXP-02 a)", async (page) => {
      await expect(page.getByText("TTB balanced", { exact: true })).toBeVisible();
      await expect(page.getByText("$17,914,500").first()).toBeVisible();
      await expect(page.getByText("$1,231,600").first()).toBeVisible();
      await noAgentVerb(page);
    });
  });

  test.fixme(
    "j08 3: fixed assets and the Larimer bonus question (TXP-03)",
    { annotation: { type: "owner", description: T06 } },
    () => {},
  );
  test.fixme(
    "j08 4: M-1/M-3 and the book-to-tax bridge (TXP-04)",
    { annotation: { type: "owner", description: T06 } },
    () => {},
  );

  test("j08 5: Schedule K equals the sum of five K-1s on every line", async ({ journey }) => {
    await journey.as("samuel-ito", REVIEW("schedule-k"), { scenario: "TXP-05:a", flags: FLAGS });
    await journey.step("J08 step 5: K = Σ K-1s and line 2 crossfoots (TXP-05 a)", async (page) => {
      await expect(page.getByText("Schedule K = Σ K-1s", { exact: true })).toBeVisible();
      const line2 = page.getByRole("row", { name: /Net rental real estate income/ });
      await expect(line2).toContainText("1,231,600");
      await expect(line2).toContainText("400,270");
      await expect(line2).toContainText("tie");
      await expect(page.getByText(/\$/)).toHaveCount(0); // "$" only on TXP-02 (T-05 §5.4)
    });
  });

  test("j08 6: Samuel signs off the allocation structure at L3 and each allocation cell's citation opens the LPA page", async ({
    journey,
  }) => {
    await journey.as("samuel-ito", `${REVIEW("schedule-k")}?ov=allocation`, {
      scenario: "TXP-06:c",
      flags: FLAGS,
    });
    await journey.step(
      "J08 step 6: the structure is pending approval (TXP-06 c)",
      async (page) => {
        await expect(page.getByText(/Pending approval/).first()).toBeVisible();
        await noAgentVerb(page);
      },
    );
    await journey.as("samuel-ito", `${REVIEW("schedule-k")}?ov=allocation`, {
      scenario: "TXP-06:a",
      flags: FLAGS,
    });
    await journey.step(
      "J08 step 6: approved, the two periods of 628,100 (TXP-06 a)",
      async (page) => {
        await expect(page.getByText(/Approved/).first()).toBeVisible();
        await expect(page.getByText(/628,100/).first()).toBeVisible();
      },
    );
  });

  test("j08 7: the M-2 fix approved in TXP-10 creates a checkpoint, Run 3 re-runs capital and K-1s, and ending capital ties at 6,866,200", async ({
    journey,
  }) => {
    await journey.as("samuel-ito", REVIEW("capital"), { scenario: "TXP-07:a", flags: FLAGS });
    await journey.step("J08 step 7: M-2 ties is off 6,200 (TXP-07 a)", async (page) => {
      await expect(page.getByText("off 6,200").first()).toBeVisible();
      await expect(page.getByText("6,860,000").first()).toBeVisible();
    });
    await journey.step(
      "J08 step 7: Sign off… is blocked while the tie is off (TXP-07 b2)",
      async (page) => {
        await page.getByRole("button", { name: "Sign off…" }).click();
        await expect(page.getByRole("button", { name: "Sign off…" })).toBeVisible();
        await noAgentVerb(page);
      },
    );
    await journey.as("olivia-brandt", `${RETURN}/issues`, { scenario: "TXP-10:a", flags: FLAGS });
    await journey.step(
      "J08 step 7: the review point and its proposed fix (TXP-10 a)",
      async (page) => {
        await expect(
          page.getByText("Tax-exempt interest 6,200 omitted from the capital rollforward").first(),
        ).toBeVisible();
      },
    );
    await journey.as("olivia-brandt", RETURN, { scenario: "TXP-00:b", flags: FLAGS });
    await journey.step("J08 step 7: Run 3 re-runs three at once (TXP-00 b)", async (page) => {
      await expect(page.getByText("3 steps running at once.")).toBeVisible();
      await expect(page.getByText("7 of 10 complete")).toBeVisible();
    });
    await journey.as("olivia-brandt", `${RETURN}/issues`, { scenario: "TXP-10:d", flags: FLAGS });
    await journey.step(
      "J08 step 7: resolved, five review points left (TXP-10 d)",
      async (page) => {
        await expect(
          page.getByText("Tax-exempt interest 6,200 omitted from the capital rollforward"),
        ).toHaveCount(0);
      },
    );
    await journey.as("olivia-brandt", `${RETURN}/workpaper`, {
      scenario: "TXP-11:b2",
      flags: FLAGS,
    });
    await journey.step(
      "J08 step 7: H8:H12 sum to 6,200 in the workbook (TXP-11 b2)",
      async (page) => {
        for (const v of ["124", "2,356", "2,015", "155", "1,550"]) {
          await expect(page.getByRole("gridcell", { name: v, exact: true }).first()).toBeVisible();
        }
      },
    );
    await journey.as("samuel-ito", REVIEW("capital"), { scenario: "TXP-07:c", flags: FLAGS });
    await journey.step("J08 step 7: ending capital ties at 6,866,200 (TXP-07 c)", async (page) => {
      await expect(page.getByText("6,866,200").first()).toBeVisible();
      await expect(page.getByText("off 6,200")).toHaveCount(0);
    });
  });

  test.fixme(
    "j08 8: inside and outside basis (TXP-08)",
    { annotation: { type: "owner", description: T06 } },
    () => {},
  );
  test.fixme(
    "j08 9: states and PTET (TXP-09)",
    { annotation: { type: "owner", description: T06 } },
    () => {},
  );

  test("j08 10: the §754 issue goes to Owen Calder as a POR-04 request in template wording", async ({
    journey,
  }) => {
    await journey.as("olivia-brandt", `${RETURN}/issues`, { scenario: "TXP-10:b", flags: FLAGS });
    await journey.step(
      "J08 step 10: §754 waits on the client, sent to Owen Calder (TXP-10 b)",
      async (page) => {
        await expect(
          page.getByText(/§754 election: partners' decision and support/).first(),
        ).toBeVisible();
        await expect(page.getByText(/sent to Owen Calder Sep 11/).first()).toBeVisible();
      },
    );
  });

  test("j08 11: the memo is adopted, approved at 9:40 and goes stale after the fix", async ({
    journey,
  }) => {
    await journey.as("samuel-ito", REVIEW("summary"), { scenario: "TXP-01:a", flags: FLAGS });
    await journey.step("J08 step 11: adopted, awaiting the reviewer (TXP-01 a)", async (page) => {
      await expect(
        page.getByText("Ridgeline Property Partners, LP — 2025 Form 1065 preparer memo").first(),
      ).toBeVisible();
      await expect(page.getByRole("button", { name: "Approve memo…" })).toBeVisible();
      await expect(page.getByText(/••-•••0287/).first()).toBeVisible(); // the EIN stays masked
    });
    await journey.as("samuel-ito", REVIEW("summary"), { scenario: "TXP-01:c", flags: FLAGS });
    await journey.step("J08 step 11: approved (TXP-01 c)", async (page) => {
      await expect(page.getByRole("button", { name: "Approve memo…" })).toHaveCount(0);
    });
    await journey.as("samuel-ito", REVIEW("summary"), { scenario: "TXP-01:d", flags: FLAGS });
    await journey.step("J08 step 11: stale after the fix (TXP-01 d)", async (page) => {
      await expect(page.getByText(/Ending capital 6,860,000 → 6,866,200/).first()).toBeVisible();
      await expect(page.getByRole("button", { name: "Regenerate sections" })).toBeVisible();
    });
  });
});

// The K-1 package (T-02-T32; TXP-12): steps 12 and 16 on TXP-12's artboards, and the portal side
// on POR-13's own states. Staging waits on T-02's live swaps.
test.describe("J08 · K-1 package", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", K1_OWNER);
  });

  test("j08 12: draft K-1s reach the Feld and Shah returns and never a portal user", async ({
    journey,
  }) => {
    await journey.as("olivia-brandt", artboard("TXP-12", "a4"));
    await journey.step("J08 step 12: drafts shared (TXP-12 A4)", async (page) => {
      await expect(
        page.getByText("Drafts block final approval of the receiving return.").first(),
      ).toBeVisible();
    });
  });

  test("j08 13–16: final approval lists entity blockers until clear; export and release run on the T-01 and T-02 screens", async ({
    journey,
  }) => {
    await journey.as("samuel-ito", artboard("TXP-12", "a"));
    await journey.step(
      "J08 steps 13–14: release waits on final approval (TXP-12 A)",
      async (page) => {
        await expect(page.getByText("Release blocked: final approval").first()).toBeVisible();
      },
    );
    await journey.as("samuel-ito", artboard("TXP-12", "a5"));
    await journey.step("J08 step 16: release ready (TXP-12 A5)", async (page) => {
      await expect(
        page
          .getByText("Portal · My K-1s (POR-13), with an invite email to each recipient")
          .first(),
      ).toBeVisible();
    });
    await journey.as("samuel-ito", artboard("TXP-12", "b"));
    await journey.step("J08 step 16: released, one invite bounced (TXP-12 B)", async (page) => {
      await expect(page.getByText("Invite email bounced — update address").first()).toBeVisible();
    });
    await journey.as("pell-street-member", "/k1s", {
      scenario: "POR-13:c",
      clock: "2026-09-15T09:24:00-05:00",
    });
    await journey.step(
      "J08 step 16: Pell Street Ventures' own package (POR-13c)",
      async (page) => {
        await expect(page.getByText("400,270").first()).toBeVisible();
        await expect(page.getByText(/Pell Street II/)).toHaveCount(0);
        await expect(page.getByText(/Accrued/)).toHaveCount(0);
      },
    );
    await journey.as("meera-shah", "/k1s", { scenario: "POR-13:f" });
    await journey.step("J08 step 16: Meera under role union (POR-13f)", async (page) => {
      await expect(
        page.getByText("Your K-1s are in Deliverables › My K-1s").first(),
      ).toBeVisible();
      await expect(page.getByText(/Accrued/)).toHaveCount(0);
    });
  });
});
