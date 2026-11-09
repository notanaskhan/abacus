// R-02-T13 (TASK-6313): the portal slice foots, and agrees with the figures book.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  ACCRUED_EXPENSES,
  ACCRUED_LINES,
  APPROVALS_AFTER,
  K1_BOXES,
  PAGE_2,
  POSTED,
  RECEIVABLE_LINES,
  UNCORRECTED,
} from "./portal-r02";

const { process } = globalThis as unknown as { process: { cwd: () => string } };
const BOOK = JSON.parse(
  readFileSync(
    join(
      process.cwd(),
      "..",
      "..",
      "backend",
      "tests",
      "golden",
      "scenario",
      "brightwater_hale",
      "portal_figures.json",
    ),
    "utf8",
  ),
) as {
  posted_entries: { total: string; accrued_expenses: { total: string } };
  uncorrected_misstatements: { net_effect: string };
  fs_draft: { page_2: { net_assets: string } };
  k1: { boxes: Record<string, string> };
};

const cents = (xs: readonly string[]): number =>
  xs.reduce((n, x) => n + Math.round(Number(x) * 100), 0);

describe("R-02-T13 portal slice", () => {
  it("Copperleaf's posted entries foot to 35,300 and accrued expenses to 14,900", () => {
    expect(cents(POSTED)).toBe(3_530_000);
    expect(cents(ACCRUED_EXPENSES)).toBe(1_490_000);
    expect(String(cents(POSTED) / 100)).toBe(BOOK.posted_entries.total);
    expect(String(cents(ACCRUED_EXPENSES) / 100)).toBe(BOOK.posted_entries.accrued_expenses.total);
  });

  it("the uncorrected misstatements net to 22,250 = 35,300 − 13,050", () => {
    expect(cents([UNCORRECTED.increase]) - cents([UNCORRECTED.decrease])).toBe(2_225_000);
    expect(UNCORRECTED.net).toBe(BOOK.uncorrected_misstatements.net_effect);
    expect(cents(ACCRUED_LINES)).toBe(1_305_000);
    expect(cents(RECEIVABLE_LINES)).toBe(4_860_000);
  });

  it("page 2 nets to 16,861,000 = 16,500,000 + 361,000", () => {
    expect(cents(PAGE_2.investments) + cents(PAGE_2.receivables)).toBe(1_686_100_000);
    expect(PAGE_2.netAssets).toBe(BOOK.fs_draft.page_2.net_assets);
  });

  it("Meera's K-1 reads 468,008 in box 2", () => {
    expect(K1_BOXES["2"]).toBe("468008");
    expect(K1_BOXES).toEqual(BOOK.k1.boxes);
  });

  it("after Sep 25, two entries accepted and two declined, one acknowledgement waiting", () => {
    expect(APPROVALS_AFTER.counts).toEqual({ waiting: 1, posted: 0, approved: 2, declined: 2 });
  });
});
