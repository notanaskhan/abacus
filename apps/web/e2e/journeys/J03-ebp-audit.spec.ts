// J03 EBP audit (P-06-T25; blueprint §7.3): the PBC requests on the Northwind 401(k) binder.
// Marcus Delaney composes the ERISA fidelity bond request (SHL-14a) and later delegates the
// bridge letter to Sam Ortiz, scoped to that one request (SHL-14b). Each step runs axe and INV-1
// to INV-5. In the fixture project the steps walk SHL-14's own scenarios laid over the seed
// (`?scenario=`); the other projects wait for `binders.engine` on in E0 and the live swap.
import type { Page } from "@playwright/test";
import { expect, test } from "../harness";

const LIVE = "binders.engine is off in E0; the BND-02 and SHL-14 live swap is P-06-T16's";
const FLAGS = ["binders.engine"];

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

/** The composer's menu field (`Category`, `Client assignee`, `Third party`): open it, pick one. */
async function choose(page: Page, label: RegExp, option: string): Promise<void> {
  const drawer = page.getByRole("dialog");
  await drawer.getByRole("button", { name: label }).focus();
  await page.keyboard.press("ArrowDown");
  await page.getByRole("menu").getByText(option, { exact: true }).click();
}

test.describe("J03", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", LIVE);
  });

  test("j03 4: Marcus composes the ERISA fidelity bond request and Hannah publishes the PBC binder", async ({
    journey,
  }) => {
    await journey.as("marcus-delaney", "/binders/_binderId_?ov=request:new:_binderId_", {
      scenario: "SHL-14:a",
      flags: FLAGS,
    });
    await journey.step(
      "J03 step 4: the composer, a new request on the Northwind binder (SHL-14a)",
      async (page) => {
        await expect(page.getByRole("heading", { name: "New request" })).toBeVisible();
        await expect(page.getByRole("dialog").getByLabel("Due")).toHaveValue("2026-09-21");
      },
    );
    await journey.step(
      "J03 step 4: Marcus writes it and sends, a person's click",
      async (page) => {
        const drawer = page.getByRole("dialog");
        await drawer
          .getByLabel("Request", { exact: true })
          .fill("ERISA fidelity bond — 2025 declarations page");
        await drawer
          .getByLabel("Description")
          .fill(
            "ERISA §412 requires a fidelity bond of at least 10% of plan assets handled, capped at $500,000 for this plan.",
          );
        await choose(page, /^Category/, "Plan documents");
        await choose(page, /^Client assignee/, "Dana Kowalski");
        await drawer.getByRole("button", { name: "Save & send" }).click();
        await expect(page.getByText("Request sent to Dana Kowalski").first()).toBeVisible();
      },
    );
  });

  test.fixme(
    "j03 4 (publish): Hannah publishes the Northwind PBC binder",
    owner(
      "P-06 · P-06-T16 BND-02 live swap: the fixtures publish only the Feld binder (BND-02 b → a), not a Northwind PBC Draft · S6, Fri Jan 22, 2027",
    ),
    async ({ journey }) => {
      await journey.as("hannah-leclerc", "/binders", { flags: FLAGS });
    },
  );

  test("j03 10: the bridge-letter request is delegated to Sam Ortiz and scoped to one request", async ({
    journey,
  }) => {
    await journey.as("marcus-delaney", "/binders/_binderId_?ov=request:_requestId_:_binderId_", {
      scenario: "SHL-14:b",
      flags: FLAGS,
    });
    await journey.step(
      "J03 step 10: the bridge letter, requested Sep 1 (SHL-14b)",
      async (page) => {
        const drawer = page.getByRole("dialog");
        await expect(drawer.getByText("Requested Sep 1 · due Sep 25")).toBeVisible();
        await expect(drawer.getByLabel("Request", { exact: true })).toHaveValue(
          "Bridge letter — Keystone, Oct–Dec 2025",
        );
      },
    );
    await journey.step("J03 step 10: delegated to Sam Ortiz, this request only", async (page) => {
      const drawer = page.getByRole("dialog");
      await drawer.getByRole("switch", { name: "Request from a third party" }).click();
      await choose(page, /^Third party/, "Sam Ortiz");
      await expect(
        drawer.getByText("Sam sees only this request (POR-14). Dana is copied."),
      ).toBeVisible();
      await expect(drawer.getByRole("button", { name: "Save & send to Sam Ortiz" })).toBeVisible();
    });
  });
});
