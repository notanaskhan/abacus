// P-11-T32 (P-11 §1 story, AC5; NOT-01, SHL-08): a phone photo of an IRS notice goes through OCR
// on the full stack and staging, on the harness (axe and INV-1 to INV-5 after each step). Rosa
// Santos's CP14 arrives as a JPEG from the portal (POR-19 capture), UploadProcessing's `ocr` step
// reads it with Textract (synthetic document; staging only, `textract_enabled`), and NOT-01's
// intake shows the notice header fields with their regions on SHL-08, every value cited to its
// word box. Nothing here accepts, creates or sends (INV-1): a person confirms on NOT-01.
//
// The fixture project has no OCR: fixme there. Hosted runs read the synthetic upload id from the
// environment (`ABACUS_E2E_SANTOS_CP14_UPLOAD`, written by the seed's OCR slice); without it the
// test skips. Fields are compared with the synthetic document's known values, never with a model.
import { expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const UPLOAD = process.env.ABACUS_E2E_SANTOS_CP14_UPLOAD;
// The synthetic CP14's printed values (abacus_tools.synthetic scanned corpus, P-11-T28).
const EXPECTED = { notice: "CP14", tax_year: "2025", amount_due: "1,284.17" } as const;

test.describe("OCR notice intake (P-11-T32)", () => {
  test("a photographed CP14 reaches NOT-01 with cited fields", async ({ journey }) => {
    test.fixme(journey.project === "fixture", "the fixture project runs no OCR (P-11-T32)");
    test.skip(UPLOAD === undefined, "ABACUS_E2E_SANTOS_CP14_UPLOAD is not set");
    await journey.as("olivia-brandt", `/notices/intake?upload=${UPLOAD ?? ""}`);
    await journey.step("NOT-01: the OCR read the header", async (page) => {
      await expect(page.locator("[data-intake-field='notice_number']")).toContainText(
        EXPECTED.notice,
        { timeout: 120_000 },
      );
      await expect(page.locator("[data-intake-field='tax_year']")).toContainText(
        EXPECTED.tax_year,
      );
      await expect(page.locator("[data-intake-field='amount_due']")).toContainText(
        EXPECTED.amount_due,
      );
    });
    await journey.step("SHL-08: a field opens the page with its word box lit", async (page) => {
      await page.locator("[data-intake-field='amount_due']").click();
      await expect(page.locator("[data-viewer-region]").first()).toBeVisible();
      await expect(page.locator("[data-text-source='ocr']").first()).toBeVisible();
    });
    await journey.step("Nothing is created until a person confirms", async (page) => {
      await expect(page.getByRole("button", { name: "Create notice" })).toBeEnabled();
    });
  });
});
