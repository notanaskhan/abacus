// J06 individual 1040 (P-06-T25; blueprint §7.6): the preparer builds and publishes the Feld 2025
// Binder (BND-02 b → a). Each step runs axe and INV-1 to INV-5 (journey harness). In the fixture
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
});
