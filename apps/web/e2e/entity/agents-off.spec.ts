// J08 with `tax.entity_agents` off (T-05-T68; T-05 §10 item 1, §F13; SPEC-651 AC-13.1): every P0
// step completes by hand. The engagement's capabilities answer the server's `agent` reason
// (`?screen=TXP-xx&st=<state>_agents_off`, screen-scenarios.ts), so each model-backed control is
// drawn disabled with "Prepared without agents · Accrued Agent is off for this firm. Prepare this
// by hand." and never hidden behind an error, while every figure is still the code's. axe and
// INV-1 to INV-5 run after every step (journey harness).
import { expect, test } from "../harness";
import type { Page } from "@playwright/test";

const LIVE =
  "T-05-T68: full stack once T-05's slices are seeded on the stack with tax.entity_agents off";
// T-06-T69: both workspaces are the seed's entitlements now; no flag to turn on.
const FLAGS: string[] = [];
const RETURN = "/tax-returns/_returnId_";
const OFF = "Prepared without agents · Accrued Agent is off for this firm. Prepare this by hand.";

async function preparedByHand(page: Page): Promise<void> {
  await expect(page.getByRole("note").filter({ hasText: OFF }).first()).toBeVisible();
}

test.describe("J08 · agents off (T-05-T68)", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", LIVE);
  });

  test("j08 agents off: Financials maps by hand and the TB still ties", async ({ journey }) => {
    await journey.as("samuel-ito", `${RETURN}/review/financials`, {
      scenario: "TXP-02:e_agents_off",
      flags: FLAGS,
    });
    await journey.step("J08 agents off: TXP-02 e by hand", async (page) => {
      await preparedByHand(page);
      await expect(page.getByText("$1,231,600").first()).toBeVisible();
    });
  });

  test("j08 agents off: the allocation structure is keyed by hand", async ({ journey }) => {
    await journey.as("samuel-ito", `${RETURN}/review/schedule-k?ov=allocation`, {
      scenario: "TXP-06:c_agents_off",
      flags: FLAGS,
    });
    await journey.step("J08 agents off: TXP-06 c by hand", async (page) => {
      await preparedByHand(page);
    });
  });

  test("j08 agents off: Schedule K and the capital accounts are the code's", async ({
    journey,
  }) => {
    await journey.as("samuel-ito", `${RETURN}/review/schedule-k`, {
      scenario: "TXP-05:a_agents_off",
      flags: FLAGS,
    });
    await journey.step("J08 agents off: K = Σ K-1s (TXP-05 a)", async (page) => {
      const line2 = page.getByRole("row", { name: /Net rental real estate income/ });
      await expect(line2).toContainText("1,231,600");
      await expect(line2).toContainText("tie");
    });
    await journey.as("samuel-ito", `${RETURN}/review/capital`, {
      scenario: "TXP-07:c_agents_off",
      flags: FLAGS,
    });
    await journey.step("J08 agents off: ending capital 6,866,200 (TXP-07 c)", async (page) => {
      await expect(page.getByText("6,866,200").first()).toBeVisible();
    });
  });

  test("j08 agents off: an issue's fix is written by a person", async ({ journey }) => {
    await journey.as("olivia-brandt", `${RETURN}/issues`, {
      scenario: "TXP-10:a_agents_off",
      flags: FLAGS,
    });
    await journey.step("J08 agents off: TXP-10 a by hand", async (page) => {
      await page
        .getByText("Tax-exempt interest 6,200 omitted from the capital rollforward")
        .first()
        .click();
      await preparedByHand(page);
      // The fix instruction is drawn disabled with its reason, never hidden.
      await expect(page.locator("button[aria-disabled='true'][title]").first()).toBeDisabled();
    });
  });

  test("j08 agents off: the memo is written by a person", async ({ journey }) => {
    await journey.as("samuel-ito", `${RETURN}/review/summary`, {
      scenario: "TXP-01:a_agents_off",
      flags: FLAGS,
    });
    await journey.step("J08 agents off: TXP-01 a by hand", async (page) => {
      await preparedByHand(page);
      await expect(
        page.getByText("Ridgeline Property Partners, LP — 2025 Form 1065 preparer memo").first(),
      ).toBeVisible();
    });
  });
});
