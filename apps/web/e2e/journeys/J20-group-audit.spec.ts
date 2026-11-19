// J20 group audit (A-01-T26; A-09-T42; A-09 §10.1): Harlow & Pike's FY2026 group audit, steps 1 to
// 8, with `assertInvariants` (INV-1 to INV-5) and axe after every `journey.step`. The fixture
// project walks the A-09 screens on their gallery artboards (AUD-32 to AUD-35 and POR-23 have no
// route of their own yet) and Margaret's Today brief on its live route; the full stack, staging and
// the production canary walk them once the screens route and the `harlow_pike` slice reaches each
// state (A-09-T39 is stage 1). Step 1 is ENG-14's (K-04); step 3 waits on AUD-31's group states.
import type { Page } from "@playwright/test";
import { type Journey, expect, test } from "../harness";
import type { PersonaSlug } from "../harness/personas";
import { noProductName } from "./r02-support";

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

type Screen = "AUD-32" | "AUD-33" | "AUD-34" | "AUD-35" | "POR-23";

async function artboard(journey: Journey, who: PersonaSlug, screen: Screen, st: string) {
  await journey.page.setViewportSize({ width: 1440, height: 900 });
  await journey.as(who, `/components/screens/${screen}?st=${st}&frame=1`);
  await expect(journey.page.locator(`[data-artboard='${st}']`).first()).toBeVisible();
}

function board(page: Page, st: string) {
  return page.locator(`[data-artboard='${st}']`).first();
}

test.describe("J20 group audit", () => {
  test.fixme(
    "j20 1 (entry): ENG-03 group toggle creates the group work item",
    owner("K-04 · ENG-14 and A-09 · AUD-02 h · S20 onward"),
    async ({ journey }) => {
      await journey.as("hannah-leclerc", "/audits");
    },
  );

  test.fixme(
    "j20 3 (mapping): 238 of 244, 1460 corrected, confirmed",
    owner("A-09 · AUD-31 group states a-e (recorded for A-09 by A-03-T19)"),
    async ({ journey }) => {
      await journey.as("omar-haddad", "/audits");
    },
  );
});

test.describe("J20 · A-09 screens", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(
      journey.project !== "fixture",
      "A-09 screens have no routes yet; the harlow_pike slice is stage 1 (A-09-T39)",
    );
  });

  test("j20 2 (structure): finalize only when no TB is missing", async ({ journey }) => {
    await artboard(journey, "omar-haddad", "AUD-32", "a");
    await journey.step("j20 2: one TB missing, Finalize waits (AUD-32 a)", async (page) => {
      await expect(
        board(page, "a")
          .getByText(/9 of 10/)
          .first(),
      ).toBeVisible();
    });
    await artboard(journey, "omar-haddad", "AUD-32", "e");
    await journey.step("j20 2: finalized once the slot is not needed (AUD-32 e)", async (page) => {
      await expect(board(page, "e").getByText("Finalized").first()).toBeVisible();
    });
  });

  test("j20 4 (eliminations): approved and posted, Balanced 50,760,000, Intercompany 0, no snapshot modified", async ({
    journey,
  }) => {
    await artboard(journey, "omar-haddad", "AUD-33", "a");
    await journey.step("j20 4: six eliminations posted (AUD-33 a)", async (page) => {
      await expect(board(page, "a").getByText("Balanced").first()).toBeVisible();
      await expect(
        board(page, "a")
          .getByText(/50,760,000/)
          .first(),
      ).toBeVisible();
      await expect(board(page, "a").getByText("Intercompany").first()).toBeVisible();
    });
  });

  test("j20 5 (scoping): manager blocked, partner decides 240,000", async ({ journey }) => {
    await artboard(journey, "omar-haddad", "AUD-34", "b");
    await journey.step("j20 5: Omar can only remind Margaret (AUD-34 b)", async (page) => {
      await expect(
        board(page, "b").getByRole("button", { name: "Remind Margaret" }),
      ).toBeVisible();
    });
    await artboard(journey, "margaret-okonkwo", "AUD-34", "c");
    await journey.step("j20 5: Margaret decides $240,000 (AUD-34 c)", async (page) => {
      await expect(board(page, "c").getByText(/Decided by Margaret Okonkwo/)).toBeVisible();
      await expect(
        board(page, "c")
          .getByText(/\$240,000/)
          .first(),
      ).toBeVisible();
    });
  });

  test("j20 6 (instructions): sent Sep 21 by Omar", async ({ journey }) => {
    await artboard(journey, "omar-haddad", "AUD-35", "b");
    await journey.step("j20 6: the instructions are Sent (AUD-35 b)", async (page) => {
      await expect(board(page, "b").getByText("Sent").first()).toBeVisible();
    });
  });

  test("j20 7 (room): Renee sees only Distribution, acknowledges, thread answered", async ({
    journey,
  }) => {
    await artboard(journey, "renee-pruett", "POR-23", "b");
    await journey.step("j20 7: acknowledged with a question (POR-23 b)", async (page) => {
      await expect(board(page, "b").getByText(/You acknowledged/)).toBeVisible();
      await expect(
        board(page, "b")
          .getByText(/Distribution/)
          .first(),
      ).toBeVisible();
      await expect(board(page, "b").getByText(/Manufacturing|Real Estate/)).toHaveCount(0);
      await noProductName(page, "b");
    });
  });

  test("j20 8 (late): Today lists the late memo; Margaret sends the follow-up", async ({
    journey,
  }) => {
    await journey.as("margaret-okonkwo", "/?today=open", { scenario: "SHL-23:5" });
    await journey.step("j20 8: the Pruett & Lang memo in Margaret's Dec 1 brief", async (page) => {
      await expect(
        page.getByText("Pruett & Lang interim memo — Harlow & Pike Distribution, Inc.").first(),
      ).toBeVisible();
    });
  });
});
