// TAX-13 a to e and not-allowed (T-03-T17) in fixture mode.
// Run: `pnpm exec playwright test --project=chromium e2e/screens/TAX-13.spec.ts`.
import { expect, test } from "@playwright/test";
import { walkBoards } from "./fixture-boards";

walkBoards("TAX-13", "/tax-returns/extensions", [
  { st: "a", ready: "Ridgeline Property Partners" },
  { st: "b", ready: "Extensions & estimates" },
  { st: "c", ready: "Extensions & estimates" },
  { st: "d", ready: "Send confirmation requests" },
  { st: "e", ready: "IND-031-04" },
  { st: "not-allowed", ready: "Submit for approval" },
]);

test("TAX-13d: the sheet says requests, never tasks (DV-TAX-13-1)", async ({ page }) => {
  await page.goto("/tax-returns/extensions?screen=TAX-13&st=d");
  await expect(page.getByRole("button", { name: "Send confirmation requests" })).toBeVisible();
  await expect(page.getByText("Send confirmation tasks")).toHaveCount(0);
});
