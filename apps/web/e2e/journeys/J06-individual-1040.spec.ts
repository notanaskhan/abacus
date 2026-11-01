// J06 individual 1040 (P-06-T25; blueprint §7.6): the preparer builds and publishes the Feld 2025
// Binder (BND-02 b → a). P-04-T47 adds the coordination step: the CCH Axcess import approved by
// Samuel Ito as a checkpoint on SHL-16 (P-04 §10 item 1). Each step runs axe and INV-1 to INV-5 (journey harness). In the fixture
// project the step walks BND-02's own scenario (`?screen=`, G-01-T16); the other
// projects wait for `binders.engine` on in E0 and the BND-02 live swap (P-06-T16) and keep it fixme.
import { expect, test } from "../harness";

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
