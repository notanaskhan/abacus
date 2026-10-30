// T-01's five screens on fixtures (T-01-T09; docs/screens/{CLI-05,ADM-05,ADM-08,TAX-09,TAX-12}.md):
// the figures the handoff's specs foot, typed against the C19 and engine-bridge stubs. Rows are
// the specs' (ADM-05 tiles, the Feld 2025 engine values and payment instructions, the Whitley
// transcript difference, Ridgeline's PTET); ids are stable. The designed tables' remaining rows
// arrive with each screen's build task (T13, T22, T35, T43), which reads its spec in full.
import type { ConsentSummaryOut, PaymentInstructionOut } from "@abacus/api-client";
import { stableId } from "./prng";

/** ADM-05 a: the status tiles (212 Signed · 2 Expiring · 1 Requested · 1 Expired · 1 Declined ·
 * 1 Revoked = 218) and AI-use 211 + Ferris + Stein + Thornbury (not requested) = 214. */
export const CONSENT_SUMMARY: ConsentSummaryOut = {
  total: 218,
  signed: 212,
  expiring: 2,
  requested: 1,
  expired: 1,
  declined: 1,
  revoked: 1,
  ai_use_signed: 211,
  offshore: 0,
};
export const AI_USE_ENGAGEMENTS = { signed: 211, ferris: 1, stein: 1, thornbury: 1 } as const;
export const VISIBLE_ROWS = 14;

/** TAX-09 e and the export file: Feld 2025's 2026 federal estimate (110% of the 2025 tax, less
 * withholding, in four payments) and the state-sourced income the engine allocates. */
export const FELD_ESTIMATE = {
  tax2025: 123_223,
  safeHarbourPct: 110,
  withholding: 55_585,
  quarters: 4,
  quarterly: 19_990,
} as const;
export const FELD_STATE_INCOME = [
  { jurisdiction: "IL", label: "IL-1040 Schedule NR — Illinois-source income", amount: 141_634 },
  // The spec names only the Illinois row's label; the others are known by jurisdiction.
  { jurisdiction: "CO", label: null, amount: 96_989 },
  { jurisdiction: "NY", label: null, amount: 69_277 },
] as const;
export const FELD_STATE_TOTAL = 307_900;

/** TAX-12 C: the payment instructions card (refund 123,476 − 123,223 = 253; NY 52,805 − 51,536 =
 * 1,269 due; NY estimate 110% × 52,805 = 58,086 − 26,790 = 31,296 ÷ 4 = 7,824). */
export const FELD_PAYMENTS: readonly PaymentInstructionOut[] = [
  { jurisdiction: "US", kind: "refund", amount: "253", due_on: null },
  { jurisdiction: "NY", kind: "balance_due", amount: "1269", due_on: "2026-04-15" },
  { jurisdiction: "US", kind: "estimate", amount: "19990", due_on: "2027-01-15" },
  { jurisdiction: "NY", kind: "estimate", amount: "7824", due_on: "2027-01-15" },
];
export const FELD_REFUND = { paid: 123_476, tax: 123_223 } as const;
export const FELD_NY = { tax: 52_805, withheld: 51_536, withholdingCredits: 26_790 } as const;

/** CLI-05 a: the Whitley TY2024 wage-and-income transcript against the return as filed: 1,870.00
 * + 1,250.00 = 3,120.00 unreported interest; 22% × 3,120.00 = 686.40; interest 66.61 to Aug 24,
 * 2026; 753.01 due. Amounts in cents. */
export const WHITLEY_DIFFERENCES = [
  { form: "1099-INT", cents: 187_000 },
  { form: "1099-INT", cents: 125_000 },
] as const;
export const WHITLEY_TOTAL_CENTS = 312_000;
export const WHITLEY_TAX_CENTS = 68_640;
export const WHITLEY_INTEREST_CENTS = 6_661;
export const WHITLEY_DUE_CENTS = 75_301;

/** CLI-05 e: Ridgeline's 2025 PTET elections by state. */
export const RIDGELINE_PTET = [28_044, 17_070, 18_982] as const;

export const FELD_RETURN_ID = stableId("tax-return:feld-2025-1040");
export const WHITLEY_ENTITY_ID = stableId("client-entity:whitley-household");
