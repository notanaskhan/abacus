// J06 individual 1040 (P-06-T25; blueprint §7.6): the preparer builds and publishes the Feld 2025
// Binder (BND-02 b → a). P-04-T47 adds the coordination step: the CCH Axcess import approved by
// Samuel Ito as a checkpoint on SHL-16 (P-04 §10 item 1). Each step runs axe and INV-1 to INV-5 (journey harness). In the fixture
// project the step walks BND-02's own scenario (`?screen=`, G-01-T16); the other
// projects wait for `binders.engine` on in E0 and the BND-02 live swap (P-06-T16) and keep it fixme.
import { expect, test } from "../harness";
import { M13, openEnvelope } from "../signatures/support";

const LIVE = "binders.engine is off in E0; the BND-02 live swap is P-06-T16's";

test.describe("J06", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", LIVE);
  });

  test("j06 2: Kevin publishes the Feld 2025 Binder and the portal shows only published requests", async ({
    journey,
  }) => {
    await journey.as("kevin-osei", "/binders/_binderId_", {
      scenario: "BND-02:b",
      flags: ["binders.engine"],
    });
    await journey.step("J06 step 2: the Draft binder, rolled forward (BND-02b)", async (page) => {
      await expect(page.getByText("Draft · 7 requests from the 2025 return")).toBeVisible();
      await expect(page.getByText("Not published")).toHaveCount(7);
    });
    await journey.step("J06 step 2: Publish to client, a person's click", async (page) => {
      await page.getByRole("button", { name: "Publish to client…" }).click();
      const dialog = page.getByRole("dialog", { name: "Publish to client" });
      await expect(dialog.getByText(/^Visible to /).first()).toBeVisible();
      await dialog.getByRole("button", { name: "Publish", exact: true }).click();
      await expect(page.getByText(/^Published /).first()).toBeVisible();
    });
    // The portal half: Claire's Documents list the binder's published requests only (POR-03a).
    await journey.as("claire-feld", "/documents"); // POR-03 a: the portal serves Claire's documents
    await journey.step(
      "J06 step 2: Claire's Documents show published requests only",
      async (page) => {
        await expect(page.getByText("Form 1095-C From Mercer Hill Health")).toBeVisible();
        await expect(page.getByText("Not published")).toHaveCount(0);
        await expect(page.getByText(/^Draft\b/)).toHaveCount(0);
      },
    );
  });

  test("j06 coordination: CCH import diff approved by Samuel Ito as a checkpoint on SHL-16", async ({
    journey,
  }) => {
    // Staging walks it once T-01's file bridge (engine import, fake CCH) creates the checkpoint.
    test.fixme(journey.project !== "fixture", "the CCH import checkpoint needs T-01-T19/T22 live");
    await journey.as(
      "samuel-ito",
      "/tax-returns/_returnId_?ov=checkpoints:tax_return:_returnId_",
      { scenario: "TAX-02:j06", flags: ["tax.returns_v1", "review.checkpoints"] },
    );
    await journey.step(
      "J06 coordination: the import is pending (SHL-16, import author)",
      async (page) => {
        await expect(page.getByText("Import pending approval").first()).toBeVisible();
        await expect(
          page.getByText("Imported from CCH Axcess 2025I:FeldJ:V3").first(),
        ).toBeVisible();
      },
    );
    await journey.step("J06 coordination: Approve checkpoint, a person's click", async (page) => {
      await page.getByRole("button", { name: /Approve checkpoint/u }).click();
      await expect(page.getByText("Out of sync").first()).toBeVisible();
    });
  });

  // K-02-T19: J06 due dates come from the platform reference sets (KNW-04 j, read-only).
  test("j06 due dates: the 1040 rule Accrued applies, read-only (KNW-04 j)", async ({
    journey,
  }) => {
    await journey.as("grace-holloway", "/knowledge/standards?section=deadline_rules", {
      scenario: "KNW-04:j",
      flags: ["knowledge.firm_standards", "rules.reference_sets"],
    });
    await journey.step("J06 due dates: Federal due-date rules · TY2025", async (page) => {
      const table = page.getByRole("table", { name: "Federal due-date rules · TY2025" });
      await expect(table).toBeVisible();
      await expect(table.getByText("15th day of the 4th month").first()).toBeVisible();
      await expect(page.getByRole("button", { name: "New version…" })).toHaveCount(0);
    });
  });

  // T-01-T46 (Playwright part 2): delivery and e-file on TAX-12's artboards and the relock on
  // TAX-09's (gallery routes in fixture mode; full stack and staging nightly once E0 carries the
  // delivery slice).
  test("j06 D: one of two signed keeps transmission locked; the ERO records it; acks accepted", async ({
    journey,
  }) => {
    await journey.as("grace-holloway", "/components/screens/TAX-12?st=a", {
      clock: "2026-09-17T09:30:00-05:00",
    });
    await journey.step("J06 D: 1 of 2 signed, Mark transmitted locked", async (page) => {
      await expect(page.getByText(/1 of 2 signed/u).first()).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Mark transmitted in CCH Axcess" }),
      ).toBeDisabled();
    });
    await journey.as("daniel-reyes", "/components/screens/TAX-12?st=c2", {
      clock: "2026-09-18T11:06:00-05:00",
    });
    await journey.step("J06 D: both signed, the ERO may record the transmission", async (page) => {
      await expect(
        page.getByRole("button", { name: "Mark transmitted in CCH Axcess" }),
      ).toBeEnabled();
    });
    await journey.as("grace-holloway", "/components/screens/TAX-12?st=d", {
      clock: "2026-09-19T09:12:00-05:00",
    });
    await journey.step(
      "J06 D: acknowledgments accepted and delivered to the portal",
      async (page) => {
        await expect(page.getByText(/return accepted/u).first()).toBeVisible();
        await expect(page.getByText(/Delivered to portal/u).first()).toBeVisible();
        await expect(page.getByRole("button", { name: /^(Approve|Send|Sign)$/u })).toHaveCount(0);
      },
    );
  });

  test("j06 relock: an approved import past tolerance supersedes the 8879", async ({
    journey,
  }) => {
    await journey.as("samuel-ito", "/components/screens/TAX-09?st=e", {
      clock: "2026-09-10T09:30:00-05:00",
    });
    await journey.step("J06 relock: the import diff names the moved figures", async (page) => {
      await expect(page.locator("[data-artboard='e']")).toBeVisible();
      await expect(
        page.getByRole("button", { name: /Approve checkpoint|Approve import/u }).first(),
      ).toBeVisible();
    });
  });

  test.fixme(
    "j28 3: Isaac Moreau exports the Granite Peak FY2026 Form 1120 after final approval",
    {
      annotation: {
        type: "owner",
        description:
          "T-01 · T-01-T46: the 1120 export needs a Granite Peak business-return scenario (T-03 forms); TAX-09 fixtures carry the Feld 1040 only",
      },
    },
    async ({ journey }) => {
      // Isaac Moreau joins the harness personas with the Granite Peak business-return slice.
      await journey.as("daniel-reyes", "/tax-returns");
    },
  );
});

// T-02-T32 (T-02 §2 "Journeys advanced"): j06 2 (Claire answers the organizer, POR-05 a → c),
// j06 4 (TAX-03 a → b: the 1095-C in, the 2024 copy ignored as wrong year), j06 5 (the Ridgeline
// Draft K-1 blocks Feld final approval, TAX-03 a and TAX-02 a) and j06 10 (Daniel's final approval
// after the release, TAX-03 d and TAX-02 e; the export is T-01's). Firm steps open the screen's
// artboard; Claire walks /questions on POR-05's own states. Staging waits on T-02's live swaps.
const T02_OWNER = "T-02-T32: T-02's screens live on staging and the canary, Thu Aug 12, 2027";

function artboard(id: string, state: string): string {
  return `/components/screens/${id}?st=${state}`;
}

test.describe("J06 · T-02 returns, organizer and K-1 dependency", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", T02_OWNER);
  });

  test("j06 2: Claire answers the organizer and marks it done", async ({ journey }) => {
    await journey.as("claire-feld", "/questions", { scenario: "POR-05:a" });
    await journey.step(
      "J06 step 2: the Feld 2025 organizer, in progress (POR-05a)",
      async (page) => {
        await expect(page.getByText("22 of 24 answered").first()).toBeVisible();
        await expect(page.getByText(/Accrued/)).toHaveCount(0);
      },
    );
    await journey.as("claire-feld", "/questions", { scenario: "POR-05:c" });
    await journey.step("J06 step 2: marked done (POR-05c)", async (page) => {
      await expect(page.getByText("Thanks — Kevin Osei has your answers.").first()).toBeVisible();
      await expect(page.getByText(/Accrued/)).toHaveCount(0);
    });
  });

  test("j06 4: Kevin files the 2025 1095-C and ignores the 2024 copy as wrong year", async ({
    journey,
  }) => {
    await journey.as("kevin-osei", artboard("TAX-03", "a"));
    await journey.step("J06 step 4: the Feld intake, 5 of 7 (TAX-03a)", async (page) => {
      await expect(page.getByText("5 of 7 requests satisfied").first()).toBeVisible();
    });
    await journey.as("kevin-osei", artboard("TAX-03", "b"));
    await journey.step("J06 step 4: the 1095-C filed, 6 of 7 (TAX-03b)", async (page) => {
      await expect(page.getByText("6 of 7 requests satisfied").first()).toBeVisible();
    });
  });

  test("j06 5: the Ridgeline Draft K-1 blocks Feld final approval", async ({ journey }) => {
    await journey.as("kevin-osei", artboard("TAX-03", "a"));
    await journey.step(
      "J06 step 5: the shared draft on the Feld intake (TAX-03a)",
      async (page) => {
        await expect(page.getByText("Draft K-1 · pre-release").first()).toBeVisible();
      },
    );
    await journey.as("daniel-reyes", artboard("TAX-02", "a"));
    await journey.step("J06 step 5: final approval blocked (TAX-02a)", async (page) => {
      await expect(page.getByText(/final approval is blocked until/).first()).toBeVisible();
    });
  });

  test("j06 10: Daniel approves the Feld return after the Ridgeline release", async ({
    journey,
  }) => {
    await journey.as("daniel-reyes", artboard("TAX-03", "d"));
    await journey.step("J06 step 10: the final K-1 replaces the draft (TAX-03d)", async (page) => {
      await expect(page.getByText("Released Sep 15").first()).toBeVisible();
    });
    await journey.as("daniel-reyes", artboard("TAX-02", "e"));
    await journey.step("J06 step 10: no draft dependency remains (TAX-02e)", async (page) => {
      await expect(page.locator("[data-artboard='e']")).toBeVisible();
      await expect(page.getByText(/final approval is blocked until/)).toHaveCount(0);
    });
  });
});

// N-02-T42 (N-02 §10.1, M13): j06 11, the Feld joint 8879. Claire has signed and Jonah has not, so
// one of two keeps transmission locked (POR-06 e); three failed identity checks route the signer
// to a handwritten signature (POR-06 h, DF-11). T-01's `j06 D3` and `relock` steps are T-01-T46's.
test.describe("J06 · N-02 the joint 8879", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", M13);
  });

  test("j06 11a: Claire signs the joint 8879 and one of two keeps transmission locked", async ({
    journey,
  }) => {
    await journey.as("claire-feld", "/sign", {
      scenario: "POR-06:e",
      clock: "2026-10-02T09:10:00-05:00",
    });
    await journey.step(
      "j06 11a: Claire signed, Jonah has his own link (POR-06 e)",
      async (page) => {
        await openEnvelope(page, /^Form 8879 · 2025 · Jonah & Claire Feld/);
        // One of the two spouses (the ERO's signature is the third): transmission stays locked.
        await expect(page.getByText("1 of 3 signed").first()).toBeVisible();
        await expect(page.getByText("Jonah Feld — Separate link").first()).toBeVisible();
        await expect(page.getByText(/Accrued/)).toHaveCount(0);
      },
    );
  });

  test("j06 11b: three failed identity checks route to a handwritten signature", async ({
    journey,
  }) => {
    await journey.as("owen-calder", "/sign", { scenario: "POR-06:h" });
    await journey.step("j06 11b: identity not verified, a paper form (POR-06 h)", async (page) => {
      await openEnvelope(page, /^Form 8879-PE · 2025/);
      await expect(page.getByText("We couldn't verify your identity.").first()).toBeVisible();
      await expect(page.getByText(/paper form to sign/).first()).toBeVisible();
    });
  });
});
