// J12-core (F-04-T26; F-04.33; blueprint §7.12): a client signs in to the firm's portal, lands
// on their to-dos, opens their documents and uploads a file. Walkable steps run on the harness in
// every project (axe and INV-1 to INV-5 after each step); a step whose screen or backend is still
// planned is `test.fixme` naming its owning epic, task and chapter 01 date (journey-e2e skill).
// The portal is white-labelled: no step may show the product's name (INV-4).
import { DEMO_INSTANT, expect, test } from "../harness";
import { M13, artboard, openEnvelope } from "../signatures/support";
import { WIDTHS, artboardAs, board, noProductName } from "./r02-support";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
// POR-01 a renders at 9:22 AM CT on E0's Monday (the handoff's artboard clock).
const SIGN_IN_CLOCK = "2026-09-14T09:22:00-05:00";
// POR-01 e's reminder link, issued Aug 20 and past its 14 days (fixtures/scenarios/POR-01.ts).
const EXPIRED_LINK = "fixture-reminder-link-feld-2026-08-20";

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("J12-core", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    // Hosted projects run only from the jobs that set their URL (F-04-T28; staging is not up yet).
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
  });

  test("J12 1: Claire Feld opens the firm's portal sign-in (POR-01a)", async ({ journey }) => {
    await journey.as("claire-feld", "/sign-in", { clock: SIGN_IN_CLOCK });
    await journey.step("J12 step 1: portal sign-in as Claire Feld", async (page) => {
      await expect(
        page.getByRole("heading", { name: "Sign in to your client portal" }),
      ).toBeVisible();
      await expect(page.getByText(/accrued/i)).toHaveCount(0);
    });
  });

  test(
    "J12 2–3: Claire types the emailed code and lands on her to-dos (POR-01b, POR-02a)",
    owner("P-08 · P-08-T10 portal sign-in BFF core · S6, Fri Jan 22, 2027"),
    async ({ journey }) => {
      // The fixture handlers answer the portal's sign-in; on the other projects the code step
      // needs the portal BFF (`/v1/portal/auth/*`), which is not built yet.
      test.fixme(journey.project !== "fixture", "the portal sign-in BFF is P-08-T10's (S6)");
      await journey.as("claire-feld", "/sign-in", { clock: SIGN_IN_CLOCK });
      const page = journey.page;
      // Any address gets the same answer (no enumeration); a synthetic one on the sink domain.
      await page.getByLabel("Email").fill("claire.feld@sink.brightwaterhale.test");
      await page.getByRole("button", { name: "Continue" }).click();
      await journey.step("J12 step 2: the code step (POR-01b)", async () => {
        await expect(page.getByRole("heading", { name: "Check your email" })).toBeVisible();
      });
      // The fixture's emailed code; the sixth digit submits.
      await page.locator("input[autocomplete='one-time-code']").first().focus();
      await page.keyboard.type("481027");
      await journey.step("J12 step 3: Claire's to-dos (POR-02a)", async () => {
        await expect(page.getByText("Upload 2 documents").first()).toBeVisible();
        await expect(page.getByText(/accrued/i)).toHaveCount(0);
      });
    },
  );

  // P-08-T26: the sign-in's other paths, in the fixture project on POR-01's own scenarios (`?st=`);
  // the full stack and staging need the emailed code from the sink mailbox (F-04-T22).
  test("J12 2b: Tess Moreno signs in with the emailed code and her authenticator (POR-01c, POR-02d)", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", "the codes come from the sink mailbox (F-04-T22)");
    await journey.as("tess-moreno", "/sign-in?st=c", { clock: SIGN_IN_CLOCK });
    const page = journey.page;
    await page.getByLabel("Email").fill("tess.moreno@sink.brightwaterhale.test");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.locator("input[autocomplete='one-time-code']").first().focus();
    await page.keyboard.type("481027");
    await journey.step("J12 step 2b: the second step (POR-01c)", async () => {
      await expect(page.getByRole("heading", { name: "Two-step verification" })).toBeVisible();
    });
    await page.getByRole("group", { name: "Authenticator code" }).locator("input").first().focus();
    await page.keyboard.type("481027");
    await page.getByRole("button", { name: "Verify" }).click();
    await journey.step("J12 step 2b: Tess's home (POR-02d)", async () => {
      await expect(page.getByRole("heading", { name: "Good morning, Tess" })).toBeVisible();
      await expect(page.getByText(/accrued/i)).toHaveCount(0);
    });
  });

  // T-01-T29 (T-01-T12's TRI predicate): a portal grant scoped to a tax_return work item asks for
  // two-step verification before return information shows. Written for the full stack; neither
  // project can walk it yet, and each says why.
  test("j12 TRI: Claire Feld completes two-step verification on her 1040 scope", async ({
    journey,
  }) => {
    test.fixme(
      journey.project === "fixture",
      "POR-01 has no TRI step-up state for Claire: its two-step frame (c) is Tess Moreno's, by firm policy; the TRI step is the live sign-in's (T-01-T12)",
    );
    test.fixme(journey.project !== "fixture", "the codes come from the sink mailbox (F-04-T22)");
    await journey.as("claire-feld", "/sign-in", { clock: SIGN_IN_CLOCK });
    const page = journey.page;
    await page.getByLabel("Email").fill("claire.feld@sink.brightwaterhale.test");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.locator("input[autocomplete='one-time-code']").first().focus();
    await page.keyboard.type("481027");
    await journey.step("J12 TRI: two-step for return information (POR-01c)", async () => {
      await expect(page.getByRole("heading", { name: "Two-step verification" })).toBeVisible();
    });
    await page.getByRole("group", { name: "Authenticator code" }).locator("input").first().focus();
    await page.keyboard.type("481027");
    await page.getByRole("button", { name: "Verify" }).click();
    await journey.step("J12 TRI: Claire's 1040 documents (POR-03a)", async () => {
      await expect(page.getByText("Form 1095-C From Mercer Hill Health")).toBeVisible();
      await expect(page.getByText(/accrued/i)).toHaveCount(0);
    });
  });

  test("J12 1e: an expired sign-in link is renewed by email (POR-01e)", async ({ journey }) => {
    test.fixme(journey.project !== "fixture", "the link comes from the sink mailbox (F-04-T22)");
    await journey.as("claire-feld", `/sign-in?st=e#link=${EXPIRED_LINK}`, {
      clock: SIGN_IN_CLOCK,
    });
    await journey.step("J12 step 1e: the expired link (POR-01e)", async (page) => {
      // The emailed link opens the card with its token; Continue asks for it and finds it expired.
      await page.getByLabel("Email").fill("claire.feld@sink.brightwaterhale.test");
      await page.getByRole("button", { name: "Continue" }).click();
      await expect(
        page.getByRole("heading", { name: "This sign-in link has expired" }),
      ).toBeVisible();
      await page.getByRole("button", { name: "Email me a new link" }).click();
      await expect(
        page.getByText("New link sent to claire.feld@sink.brightwaterhale.test"),
      ).toBeVisible();
    });
  });

  test("J12 1g: too many wrong codes pause sign-in and name the firm's contact (POR-01g)", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", "the codes come from the sink mailbox (F-04-T22)");
    await journey.as("claire-feld", "/sign-in?st=g", { clock: SIGN_IN_CLOCK });
    const page = journey.page;
    await page.getByLabel("Email").fill("claire.feld@sink.brightwaterhale.test");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.locator("input[autocomplete='one-time-code']").first().focus();
    await page.keyboard.type("481072"); // a mistyped code, on the last try
    await journey.step("J12 step 1g: Too many attempts (POR-01g)", async () => {
      await expect(page.getByRole("heading", { name: "Too many attempts" })).toBeVisible();
      await expect(page.getByText(/contact Grace Holloway at Brightwater Hale/)).toBeVisible();
    });
  });

  test("J12 role union: Meera Shah's home and her scopes, each with its role (POR-02e)", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", "the role union's homes are P-08-T23's fixtures");
    await journey.as("meera-shah", "/", { clock: DEMO_INSTANT });
    await journey.step("J12 role union: Meera's own 1040 (POR-02e)", async (page) => {
      await expect(page.getByRole("heading", { name: "Good morning, Meera" })).toBeVisible();
    });
    await journey.step("J12 role union: her scopes in the account menu", async (page) => {
      await page.getByRole("button", { name: /Meera Shah/ }).click();
      const menu = page.getByRole("menu", { name: "Account" });
      await expect(menu.getByRole("menuitemradio", { name: /Meera Shah/ })).toBeVisible();
      await expect(
        menu.getByRole("menuitemradio", { name: /Ridgeline Property Partners, LP/ }),
      ).toBeVisible();
      // Closed before the step's axe pass: the open menu is modal, so it hides the page behind it
      // (aria-hidden on #root while focus stays in the menu), which axe reads as aria-hidden-focus.
      await page.keyboard.press("Escape");
      await expect(menu).toHaveCount(0);
    });
  });

  // R-01-T21: steps 4, 5 and 15 at 1400 and on the 390 preset. Like 2–3, a signed-in portal step
  // runs on fixtures until the portal BFF answers on the other projects (P-08-T10).
  for (const width of [1400, 390] as const) {
    const at = width === 390 ? " · 390" : "";

    test(
      `J12 4: Claire opens the Feld 2025 Binder's documents and ignores one with a note (POR-03a, f)${at}`,
      owner("R-01 · R-01-T21 Playwright (POR-03) · S10, Fri Mar 19, 2027"),
      async ({ journey }) => {
        test.fixme(journey.project !== "fixture", "the portal sign-in BFF is P-08-T10's (S6)");
        await journey.page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
        await journey.as("claire-feld", "/documents", { clock: DEMO_INSTANT });
        const page = journey.page;
        await journey.step("J12 step 4: Claire's documents (POR-03a)", async () => {
          await expect(
            page.getByText("Form 1095-C From Mercer Hill Health").first(),
          ).toBeVisible();
          await expect(page.getByText(/accrued/i)).toHaveCount(0);
        });
        if (width === 390) return;
        await page.getByRole("button", { name: /^Ignore Form 1095-C/ }).click();
        const menu = page.getByRole("menu", { name: "Ignore" });
        // The note field sits beside the menu, not in it: a menu holds menu items only (ARIA).
        await page
          .getByRole("textbox", { name: "Add a note (optional)" })
          .fill("No 1095-C this year.");
        await menu.getByRole("menuitem", { name: "Already sent another way" }).click();
        await journey.step("J12 step 4: the 1095-C ignored, with Undo (POR-03f)", async () => {
          const row = page.locator("[data-request]", {
            hasText: "Form 1095-C From Mercer Hill Health",
          });
          await expect(row.getByRole("button", { name: "Undo" })).toBeVisible();
        });
      },
    );

    test(
      `J12 5: Claire opens the 1095-C request, reads why, and comments (POR-04a)${at}`,
      owner("R-01 · R-01-T21 Playwright (POR-04) · S10, Fri Mar 19, 2027"),
      async ({ journey }) => {
        test.fixme(journey.project !== "fixture", "the portal sign-in BFF is P-08-T10's (S6)");
        await journey.page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
        await journey.as("claire-feld", "/documents", { clock: DEMO_INSTANT });
        const page = journey.page;
        await page
          .getByRole("button", { name: "Form 1095-C From Mercer Hill Health" })
          .first()
          .click();
        const sheet = page.getByRole("dialog");
        await journey.step(
          "J12 step 5: the 1095-C sheet (POR-04a)",
          async () => {
            await expect(sheet.getByText("Why we need it")).toBeVisible();
            await expect(sheet.getByText("To do · requested Feb 3")).toBeVisible();
            await expect(sheet.getByText(/accrued/i)).toHaveCount(0);
          },
          { include: "[role='dialog']" },
        );
        const composer = sheet.getByPlaceholder("Write a comment…");
        await composer.fill("I'll download it tonight.");
        await composer.press("Enter");
        await journey.step(
          "J12 step 5: the comment joins the shared thread",
          async () => {
            await expect(sheet.getByText("I'll download it tonight.")).toBeVisible();
          },
          { include: "[role='dialog']" },
        );
      },
    );

    test(
      `J12 15: Sam Ortiz sees only Keystone's nine requests in his room (POR-14a)${at}`,
      owner("R-01 · R-01-T21 Playwright (POR-14) · S10, Fri Mar 19, 2027"),
      async ({ journey }) => {
        test.fixme(journey.project !== "fixture", "the portal sign-in BFF is P-08-T10's (S6)");
        await journey.page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
        await journey.as("sam-ortiz", "/requests", { clock: DEMO_INSTANT });
        const page = journey.page;
        await journey.step(
          "J12 step 15: Sam's room, 4 of 9 (POR-14a)",
          async () => {
            await expect(page.getByText("4 of 9 uploaded").first()).toBeVisible();
            // The chip at 1400, the avatar at 390 (POR-14: header with brand and avatar): one name.
            await expect(
              page.getByRole("button", { name: "Sam Ortiz · Keystone" }).first(),
            ).toBeVisible();
            await expect(page.getByText(/accrued/i)).toHaveCount(0);
          },
          // INV-4: the third party never sees the client's own documents or home.
          { outOfScope: ["Form 1095-C From Mercer Hill Health", "Upload 2 documents"] },
        );
      },
    );
  }
});

// N-02-T42 (N-02 §10.1, M13): j12 9, a client reviews, consents, signs and declines on POR-06's own
// states, and the identity-question 8879 path (d). Owen Calder is POR-06's persona.
test.describe("J12 signing (N-02-T42)", () => {
  test("j12 9: a client reviews, consents, signs, declines and reads the 8879 path", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", M13);
    await journey.as("owen-calder", "/sign", { scenario: "POR-06:a" });
    await journey.step(
      "j12 9: review, Continue waits on the last page (POR-06 a)",
      async (page) => {
        await openEnvelope(page, /^Engagement letter — Cost segregation/);
        await expect(page.getByText(/Read to page \d+ to continue\./).first()).toBeVisible();
        await expect(page.getByText(/Accrued/)).toHaveCount(0);
      },
    );
    // POR-06 c is the provider's return (`/sign/<id>/return?session=`), whose session id only the
    // provider hands back: the fixture walk reads c's own artboard, the hosted walk the real return.
    await journey.as("owen-calder", "/sign", { scenario: "POR-06:c" });
    await journey.step("j12 9: signed, the completion card (POR-06 c)", async (page) => {
      await page.goto(artboard("POR-06", "c"));
      await expect(page.getByText(/^Signed\. Thank you, /).first()).toBeVisible();
      await expect(page.locator("[data-artboard]").getByText(/Accrued/)).toHaveCount(0);
    });
    await journey.as("owen-calder", "/sign", { scenario: "POR-06:d" });
    await journey.step(
      "j12 9: the 8879 verifies by identity questions (POR-06 d)",
      async (page) => {
        await openEnvelope(page, /^Form 8879-PE · 2025/);
        await expect(page.getByText("Identity questions").first()).toBeVisible();
      },
    );
    await journey.as("owen-calder", "/sign", { scenario: "POR-06:g" });
    await journey.step("j12 9: declined (POR-06 g)", async (page) => {
      await expect(page.getByText(/[Dd]eclined/).first()).toBeVisible();
    });
  });
});

// R-02-T23 (R-02 §5.6): steps 8 and 10 and the scoped-identity lines on POR-08 and POR-09, in the
// fixture project at 1400 and 390. J12 P0 core is walkable once POR-09 is live (Fri Mar 3, 2028).
test.describe("J12 · R-02 approvals and deliverables", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(
      journey.project !== "fixture",
      "R-02's live swap (R-02-T28) and the batch deploy; POR-08 a–d stay fixture (C-02, A-08)",
    );
  });

  for (const width of WIDTHS) {
    const at = width === 390 ? " · 390" : "";
    test(`j12 8: Dana accepts AJE-1 and RJE-1, declines PAJE-1 and PAJE-2 with reasons and acknowledges the 22,250 net effect${at}`, async ({
      journey,
    }) => {
      await artboardAs(journey, "dana-kowalski", "POR-08", "e", width);
      await journey.step(`j12 8: Dana's four attest entries (POR-08 e)${at}`, async (page) => {
        for (const amount of ["$48,600.00", "$14,850.00", "$35,300.00", "$13,050.00"]) {
          await expect(board(page, "e").getByText(amount).first()).toBeVisible();
        }
        await expect(board(page, "e").getByRole("button", { name: "Accept" })).toHaveCount(4);
        await noProductName(page, "e");
      });
      await artboardAs(journey, "dana-kowalski", "POR-08", "e2", width);
      await journey.step(
        `j12 8: recorded, and 22,250 acknowledged (POR-08 e2)${at}`,
        async (page) => {
          await expect(
            board(page, "e2").getByText(/Accepted by Dana Kowalski · Sep 25/),
          ).toHaveCount(2);
          await expect(
            board(page, "e2").getByText("Not recorded · Sep 25 · Recorded when invoiced"),
          ).toBeVisible();
          await expect(board(page, "e2").getByText(/\$22,250\.00 in total/)).toBeVisible();
          await noProductName(page, "e2");
        },
      );
    });

    test(`j12 8 (fixture): Ben asks about accrued expenses and Tess approves the August package${at}`, async ({
      journey,
    }) => {
      await artboardAs(journey, "ben-ashby", "POR-08", "a", width);
      await journey.step(`j12 8: the August package waits (POR-08 a)${at}`, async (page) => {
        await expect(board(page, "a").getByText(/Revenue rose 4.5% to \$214,600/)).toBeVisible();
        await expect(
          board(page, "a").getByText("Prepared by Brightwater Hale. No assurance is provided."),
        ).toBeVisible();
      });
      await artboardAs(journey, "ben-ashby", "POR-08", "d", width);
      await journey.step(`j12 8: Ask about this entry (POR-08 d)${at}`, async (page) => {
        await expect(board(page, "d").getByRole("button", { name: "Send" })).toBeVisible();
      });
      await artboardAs(journey, "tess-moreno", "POR-08", "b", width);
      await journey.step(`j12 8: approved by Tess Moreno (POR-08 b)${at}`, async (page) => {
        await expect(
          board(page, "b")
            .getByText(/Tess Moreno/)
            .first(),
        ).toBeVisible();
        await expect(board(page, "b").getByRole("button", { name: "Approve" })).toHaveCount(0);
      });
    });

    test(`j12 10: Dana comments on page 2, approves draft v4 and downloads the finals after release${at}`, async ({
      journey,
    }) => {
      await artboardAs(journey, "dana-kowalski", "POR-09", "a", width);
      await journey.step(
        `j12 10: the draft for review, page 2 of 14 (POR-09 a)${at}`,
        async (page) => {
          await expect(board(page, "a").getByText("Draft for review")).toBeVisible();
          await expect(board(page, "a").getByText("2 / 14")).toBeVisible();
          await expect(
            board(page, "a").getByText(
              "Keystone calls these participant loans. Can the note say both?",
            ),
          ).toBeVisible();
        },
      );
      await artboardAs(journey, "dana-kowalski", "POR-09", "b", width);
      await journey.step(`j12 10: approved, the watermark stays (POR-09 b)${at}`, async (page) => {
        await expect(board(page, "b").getByRole("button", { name: "Approve" })).toHaveCount(0);
      });
      await artboardAs(journey, "dana-kowalski", "POR-09", "c", width);
      await journey.step(`j12 10: the finals with Download (POR-09 c)${at}`, async (page) => {
        await expect(
          board(page, "c").getByRole("button", { name: "Download" }).first(),
        ).toBeVisible();
        await noProductName(page, "c");
      });
    });
  }

  test("j12 scoped: Meera Shah sees only her Ridgeline K-1 and Sam Ortiz has no Approvals or Deliverables", async ({
    journey,
  }) => {
    await artboardAs(journey, "meera-shah", "POR-09", "d");
    await journey.step(
      "j12 scoped: Meera's released K-1 only (POR-09 d)",
      async (page) => {
        await expect(board(page, "d").getByText("My K-1s")).toBeVisible();
      },
      { outOfScope: ["Dana Kowalski", "Northwind Robotics 401(k) Plan"] },
    );
    await journey.as("sam-ortiz", "/", { clock: DEMO_INSTANT });
    await journey.step(
      "j12 scoped: Sam Ortiz's reduced portal has no Approvals or Deliverables",
      async (page) => {
        await expect(page.getByRole("link", { name: "Approvals" })).toHaveCount(0);
        await expect(page.getByRole("link", { name: "Deliverables" })).toHaveCount(0);
      },
    );
  });
});
