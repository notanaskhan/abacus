// J13 partner review (P-01-T16; blueprint §7.13): the chrome of the partner's morning. Daniel
// Reyes signs in, sees the bell's dot and opens the notifications drawer (SHL-01, SHL-04). The rows
// are fixture until the P-04 producers land. Each step runs axe and INV-1 to INV-5.
import { DEMO_INSTANT, expect, openPalette, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};

test.describe("J13", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
  });

  test("j13 1-2 chrome: Daniel signs in, sees the bell dot and opens the notifications drawer", async ({
    journey,
  }) => {
    // The rows are SHL-04 a's fixture (the P-04 producers write them later); the fixture project
    // lays that scenario over the seed, the full stack reads the bell's own answer.
    await journey.as("daniel-reyes", "/", { clock: DEMO_INSTANT, scenario: "SHL-04:a" });
    await journey.step(
      "J13 step 1: Daniel inside the toolbar, the bell lit (SHL-01)",
      async (page) => {
        await expect(page.getByRole("navigation", { name: "Modules" })).toBeVisible();
        await expect(page.getByRole("button", { name: "Notifications, unread" })).toBeVisible();
      },
    );
    await journey.step("J13 step 2: the notifications drawer (SHL-04)", async (page) => {
      await page.getByRole("button", { name: "Notifications, unread" }).click();
      await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
    });
  });
});

// T-02-T32 (T-02 §2): j13 7-8, the K-1 release clears the draft chips on the Feld intake and Daniel
// gives the Feld final approval (TAX-03 d, TAX-02 e), on the screens' artboards in the fixture
// project; staging waits on T-02's live swaps.
test.describe("J13 · T-02 release and final approval", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(
      journey.project !== "fixture",
      "T-02-T32: T-02's screens live on staging and the canary, Thu Aug 12, 2027",
    );
  });

  test("j13 7-8: the release clears the draft chips and Daniel approves the Feld 1040", async ({
    journey,
  }) => {
    await journey.as("daniel-reyes", "/components/screens/TAX-03?st=d");
    await journey.step(
      "J13 step 7: the draft chip gives way to the final (TAX-03d)",
      async (page) => {
        await expect(page.getByText("Released Sep 15").first()).toBeVisible();
      },
    );
    await journey.as("daniel-reyes", "/components/screens/TAX-02?st=e");
    await journey.step("J13 step 8: Feld final approval unblocked (TAX-02e)", async (page) => {
      await expect(page.locator("[data-artboard='e']")).toBeVisible();
      await expect(page.getByText(/final approval is blocked until/)).toHaveCount(0);
    });
  });
});

// I-01-T22: j13 2-3 on HOME-02, Daniel's approvals queue and the Ridgeline sign-off he opens first,
// on the fixture project. The tax hosts behind a row stay fixture-only until T-05 (DV-4), so the
// live project waits on them; the audit half is j23's.
test.describe("J13 · HOME-02 queue", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", "I-01-T22: the tax hosts, T-05 (S35–S44; DV-4)");
  });

  test("j13 2-3: the queue's 11 waiting, then the memo sign-off with its evidence", async ({
    journey,
  }) => {
    await journey.as("daniel-reyes", "/home/approvals", {
      clock: DEMO_INSTANT,
      scenario: "HOME-02:a",
    });
    await journey.step("J13 step 2: 3 + 6 + 2 = 11 waiting on Daniel (HOME-02a)", async (page) => {
      const queue = page.locator("[data-home02='queue']");
      await expect(queue.getByRole("button", { name: /^Decisions\s*3/ })).toBeVisible();
      await expect(queue.getByRole("button", { name: /^Sign-offs\s*6/ })).toBeVisible();
      await expect(queue.getByRole("button", { name: /^Approvals & sends\s*2/ })).toBeVisible();
    });
    await journey.step("J13 step 3: the memo sign-off and its paper (HOME-02d)", async (page) => {
      await page.getByRole("button", { name: /Ridgeline 1065 · Summary & preparer memo/ }).click();
      await expect(page.getByRole("heading", { name: /^Summary & preparer memo/ })).toBeVisible();
      await expect(page.getByRole("button", { name: "Sign off…" })).toBeVisible();
    });
    // The memo's paper is an owner summary, fixture-only until T-05 (DV-4): the artboard shows it.
    await journey.as("daniel-reyes", "/components/screens/HOME-02?st=d");
    await journey.step("J13 step 3: the preparer memo beside it (HOME-02d)", async (page) => {
      await expect(page.locator("[data-home02='paper']")).toBeVisible();
    });
  });
});

// P-02-T12 (P-02 §10): j13 4, Daniel's Monday search. ⌘K "ridgeline" offers the Ridgeline client
// and its 2025 Form 1065, filtered by his permissions; the 1065 opens the client record (CLI-02)
// while TXP-01 is `planned` (P-02 AC "TXP-01 planned"), so the TXP-01 landing is `test.fixme`
// until T-05 registers it. The fixture project opens on SHL-02's scenario (search.palette on).
test.describe("J13 · P-02 search", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
  });

  test("j13 4: ⌘K ridgeline offers the 1065 and the client record filtered by permissions", async ({
    journey,
  }) => {
    const scenario = journey.project === "fixture" ? { scenario: "SHL-02:a" } : {};
    await journey.as("daniel-reyes", "/", { clock: DEMO_INSTANT, ...scenario });
    await journey.step("J13 step 4: ridgeline in the palette (SHL-02)", async (page) => {
      await (await openPalette(page)).fill("ridgeline");
      const clients = page.getByRole("group", { name: "Clients" });
      const returns = page.getByRole("group", { name: "Returns" });
      await expect(
        clients.getByRole("option", { name: /Ridgeline Property Partners, LP/ }),
      ).toBeVisible();
      await expect(returns.getByRole("option", { name: /2025 Form 1065/ })).toBeVisible();
    });
    await journey.step("J13 step 4: the 1065 opens the client record (CLI-02)", async (page) => {
      await page
        .getByRole("group", { name: "Returns" })
        .getByRole("option", { name: /2025 Form 1065/ })
        .click();
      await expect(page).toHaveURL(/\/clients\//);
    });
  });

  test("j13 4: the 1065 lands on TXP-01", async ({ journey }) => {
    test.fixme(true, "T-05: TXP-01");
    await journey.as("daniel-reyes", "/", { clock: DEMO_INSTANT });
  });
});
