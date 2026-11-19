// J10 month-end close (P-06-T25; blueprint §7.10): Raj Malhotra's August close intake for
// Copperleaf Coffee Roasters, hosted on BND-02 until C-01 builds CLS-03. Raj adds the ad hoc
// Sound Electric invoice to the eight recurring requests and sends it, so the binder holds nine.
// Each step runs axe and INV-1 to INV-5. No project walks it yet: SHL-14d's close fixture already
// holds the invoice (adding it again reads "7 of 10") and answers no binder rows, so the step
// waits for the BND-02 live swap or CLS-03 (C-01).
import { expect, test } from "../harness";
import { artboardAt } from "./c01-support";
import { artboardAs, board, noProductName } from "./r02-support";

const INVOICE = "Sound Electric invoice — Aug 18 ($3,200)";

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("J10", () => {
  test.fixme(
    "j10 2: Raj adds the Sound Electric invoice and publishes 9 requests",
    owner(
      "P-06 · P-06-T16 BND-02 live swap (or C-01 CLS-03): SHL-14d's fixture is the post-add state and serves no binder rows · S6, Fri Jan 22, 2027",
    ),
    async ({ journey }) => {
      await journey.as("raj-malhotra", "/binders/_binderId_?ov=request:new:_binderId_", {
        scenario: "SHL-14:d",
        flags: ["binders.engine"],
      });
      await journey.step("J10 step 2: the composer on the August close intake", async (page) => {
        await expect(page.getByRole("heading", { name: "New request" })).toBeVisible();
      });
      await journey.step(
        "J10 step 2: Raj writes the ad hoc request and sends it",
        async (page) => {
          const drawer = page.getByRole("dialog");
          await drawer.getByLabel("Request", { exact: true }).fill(INVOICE);
          await drawer.getByLabel("Due").fill("2026-09-18");
          await drawer.getByRole("button", { name: /^Save & send/ }).click();
          await expect(page.getByText(/^Request sent/).first()).toBeVisible();
        },
      );
      await journey.step("J10 step 2: the close intake holds nine requests", async (page) => {
        await expect(page.getByRole("tab", { name: /Requests\s*9/ })).toBeVisible();
        await expect(page.getByText(INVOICE).first()).toBeVisible();
      });
    },
  );

  // K-02-T19: J10 thresholds, how BH AJE thresholds v2 sorted Copperleaf's August entries (KNW-04 a).
  test("j10 thresholds: BH AJE thresholds v2 sorts Copperleaf's August entries", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", "KNW-04 examples are fixture-only until C-01");
    await journey.as("priya-raman", "/knowledge/standards?section=aje_thresholds", {
      scenario: "KNW-04:a",
      flags: ["knowledge.firm_standards"],
    });
    await journey.step("J10 thresholds: 4 within (20,020) and 1 held (14,900)", async (page) => {
      await expect(
        page.getByText("4 within threshold · 20,020 · approved as one batch by Raj Malhotra"),
      ).toBeVisible();
    });
  });
});

// R-02-T23 (R-02 §5.6): j10 11 on POR-08 (fixture project); the full stack waits on C-02 (J10 P0
// at S55).
test.describe("J10 · R-02 approvals", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", "C-02 registers the close package provider (S55)");
  });

  test("j10 11: Tess approves the August package in POR-08 on Sep 15 at 8:42 AM", async ({
    journey,
  }) => {
    await artboardAs(journey, "tess-moreno", "POR-08", "b");
    await journey.step("j10 11: approved by Tess Moreno (POR-08 b)", async (page) => {
      await expect(
        board(page, "b")
          .getByText(/Tess Moreno/)
          .first(),
      ).toBeVisible();
      await expect(
        board(page, "b").getByRole("button", { name: "Approve", exact: true }),
      ).toHaveCount(0);
      await noProductName(page, "b");
    });
  });
});

// C-01-T51 (TASK-8701; C-01 §10.1): the J10 read-only path, steps 0 to 7, on the close screens'
// own scenarios through their live routes (fixture project). `journey.step` runs axe and INV-1 to
// INV-5 after each. The full stack, staging and the canary walk them once the CAS slice carries the
// fake QBO company, the statements and Run 1/Run 2 (C-01-T44's partials) and the batch deploys.
const CLOSE = "/closes/_closeId_";
const CLOSES = ["closes.engine"];

test.describe("J10 · C-01 read-only path", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(
      journey.project !== "fixture",
      "C-01-T44 partials: fake QBO company, statements and runs in the CAS slice (C-01-T51)",
    );
  });

  test("j10 0: Priya sees August 2026 closes 3 · 11 · 5 · 3 and Copperleaf 4 days past due", async ({
    journey,
  }) => {
    await journey.as("priya-raman", "/closes", { scenario: "CLS-01:a", flags: CLOSES });
    await journey.step("j10 0: the August portfolio (CLS-01 a)", async (page) => {
      await expect(
        page.getByText("22 closes · 51 open issues · 2 past due · 3 running"),
      ).toBeVisible();
      const copperleaf = page.getByRole("row", { name: /Copperleaf Coffee Roasters/ });
      await expect(copperleaf.getByText("4 days past due")).toBeVisible();
    });
  });

  test("j10 1: plan v3 carries forward and v4 applies from September", async ({ journey }) => {
    await journey.as("priya-raman", "/close-plans/_clientId_", {
      scenario: "CLS-09:a",
      flags: CLOSES,
    });
    await journey.step("j10 1: v3 published by Priya Raman (CLS-09 a)", async (page) => {
      await expect(page.getByText(/Published .+ by Priya Raman/).first()).toBeVisible();
    });
    await journey.as("raj-malhotra", "/close-plans/_clientId_", {
      scenario: "CLS-09:b",
      flags: CLOSES,
    });
    await journey.step("j10 1: Raj's draft v4 asks Priya to publish (CLS-09 b)", async (page) => {
      await expect(page.getByText(/Draft v4/).first()).toBeVisible();
      await expect(page.getByRole("button", { name: "Request publish…" })).toBeVisible();
    });
  });

  test("j10 3: Ben uploads the savings statement and answers in POR-11", async ({ journey }) => {
    await artboardAt(journey, "ben-ashby", "POR-11", "a");
    await journey.step("j10 3: three questions on the August close (POR-11 a)", async (page) => {
      await expect(
        board(page, "a").getByText(/What was the \$3,200 payment to Sound Electric\?/),
      ).toBeVisible();
      await noProductName(page, "a");
    });
  });

  test("j10 3b: Raj incorporates the Square payouts and Run 2 starts", async ({ journey }) => {
    await journey.as("raj-malhotra", `${CLOSE}/intake`, { scenario: "CLS-03:b", flags: CLOSES });
    await journey.step("j10 3b: Square payouts incorporated (CLS-03 b)", async (page) => {
      await expect(page.getByRole("button", { name: /Re-run affected tasks/ })).toBeVisible();
    });
  });

  test("j10 4: Run 2 card 6 of 9 and its trace", async ({ journey }) => {
    await journey.as("raj-malhotra", CLOSE, { scenario: "CLS-02:overview-a", flags: CLOSES });
    await journey.step("j10 4: Run 2 running, 6 of 9 (CLS-02 A)", async (page) => {
      await expect(page.getByText(/6 of 9 complete/).first()).toBeVisible();
    });
  });

  test("j10 4d: Raj answers the Square decision card", async ({ journey }) => {
    await journey.as("raj-malhotra", CLOSE, { scenario: "CLS-02:overview-d", flags: CLOSES });
    await journey.step("j10 4d: Run 2 waits on the Square treatment (CLS-02 D)", async (page) => {
      await expect(page.getByText(/Square/).first()).toBeVisible();
    });
  });

  test("j10 5: ••4410 reconciles to 0.00 and Raj signs L1", async ({ journey }) => {
    await journey.as("raj-malhotra", `${CLOSE}/accounts/_accountRef_`, {
      scenario: "CLS-05:d",
      flags: CLOSES,
    });
    await journey.step("j10 5: reconciled and signed (CLS-05 d)", async (page) => {
      await expect(page.getByText("Reconciled ✓").first()).toBeVisible();
    });
  });

  test("j10 5b: prepaid insurance ties once AJE-02 is recorded in QuickBooks", async ({
    journey,
  }) => {
    await journey.as("raj-malhotra", `${CLOSE}/accounts`, { scenario: "CLS-04:a", flags: CLOSES });
    await journey.step("j10 5b: the Prepaid Insurance workpaper (CLS-04 a)", async (page) => {
      await expect(page.getByText(/Prepaid Insurance/).first()).toBeVisible();
    });
  });

  test("j10 6: the Sound Electric question is answered and Priya resolves it", async ({
    journey,
  }) => {
    await journey.as("raj-malhotra", `${CLOSE}/review`, { scenario: "CLS-06:d", flags: CLOSES });
    await journey.step("j10 6: resolved at 1:20 PM, six left (CLS-06 d)", async (page) => {
      await expect(page.getByText("Exceptions 6").first()).toBeVisible();
    });
  });

  test("j10 7: Priya accepts the payroll explanation (+7,670)", async ({ journey }) => {
    await journey.as("priya-raman", `${CLOSE}/flux`, { scenario: "CLS-10:c", flags: CLOSES });
    await journey.step("j10 7: both explanations accepted (CLS-10 c)", async (page) => {
      await expect(page.getByText(/Accepted/).first()).toBeVisible();
      await expect(page.getByText(/7,670/).first()).toBeVisible();
    });
  });
});
