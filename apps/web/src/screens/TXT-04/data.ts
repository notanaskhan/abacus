// TXT-04 (T-07-T26): the Thornbury estate's figures as the handoff draws them. Totals are computed
// from the rows (never typed) so every section foots; the tests compare them with the tally.
import { count } from "@abacus/ui";
export const INVENTORY = [
  ["A", "Residence — 2150 N. Lincoln Park West, Chicago", 3_850_000, 3_790_000, 3_850_000, "Appraisal, Mar 2026", "Valued"],
  ["B", "Harborline brokerage account ••7731 — marketable securities", 8_240_000, 7_965_000, 8_240_000, "Statement + DOD pricing", "Valued"],
  ["C", "Cash — First Lakeshore Bank checking and money market", 412_000, 412_000, 412_000, "Statements", "Valued"],
  ["D", "Life insurance — Lakeview Mutual policy (Form 712), payable to Paul Thornbury", 1_000_000, 1_000_000, null, "Form 712 requested", "Gathering"],
  ["F", "Tangible personal property — household contents and art", 186_000, 186_000, 186_000, "Appraisal requested", "Gathering"],
  ["I", "Harborline IRA ••2208 — beneficiary Paul Thornbury (income in respect of a decedent; no step-up)", 2_712_000, 2_640_000, null, "Statement", "Valued"],
] as const; // prettier-ignore
export const DEDUCTIONS = [
  ["Schedule J funeral expenses", 28_500],
  ["Schedule J administration expenses (legal, executor, appraisal; estimated)", 240_000],
  ["Schedule K debts of the decedent", 131_500],
  ["Schedule O charitable bequest — Lincoln Park Conservancy", 500_000],
] as const;
export const GIFTS = [
  ["2023", "Paul Thornbury", "Cash", 1_217_000, 17_000],
  ["2024", "Paul Thornbury", "Cash", 18_000, 18_000],
  ["2025", "Paul Thornbury", "Cash", 19_000, 19_000],
  ["2026 (Jan 10)", "Paul Thornbury", "Cash", 19_000, 19_000],
] as const;
export const TALLY = {
  gross: 16_400_000,
  deductions: 900_000,
  taxable: 15_500_000,
  adjustedGifts: 1_200_000,
  exclusion: 18_000_000,
} as const;

/** Whole dollars, grouped, no "$" (the statement grammar). */
export const fmt = (n: number): string => count(n);
export const sum = (xs: readonly number[]): number => xs.reduce((a, b) => a + b, 0);
export const grossEstate = (): number => sum(INVENTORY.map((r) => r[2]));
export const totalDeductions = (): number => sum(DEDUCTIONS.map((r) => r[1]));
export const adjustedTaxableGifts = (): number => sum(GIFTS.map((g) => g[3] - g[4]));
