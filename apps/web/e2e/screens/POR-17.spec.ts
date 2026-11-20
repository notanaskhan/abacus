// POR-17 (A-08-T37 screen spec): the respondent page's a, d and e from the gallery, at 1400 and
// 390, axe at zero serious or critical in light and forced colors; an expired link names no firm
// (DV-7). b, c and f need the respondent's typing or another respondent's seed (TASK-8756 gaps).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/POR-17.spec.ts`.
import { expect, test } from "@playwright/test";
import { walkGallery } from "./gallery-boards";

walkGallery("POR-17", ["a", "d", "e"]);
walkGallery("POR-17", ["a"], { width: 390 });

test("POR-17d: an expired link names no firm (DV-7)", async ({ page }) => {
  await page.goto("/components/screens/POR-17?st=d&frame=1");
  await expect(page.getByText("This confirmation link has expired")).toBeVisible();
  await expect(page.getByText(/Brightwater/)).toHaveCount(0);
});
