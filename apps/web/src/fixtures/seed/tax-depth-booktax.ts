// T-06-T30 (TASK-8752): Ridgeline's 2025 book-tax schedules in fixture mode, as the depth routes
// answer them (TXP-04 a–d): Schedule M-3 (required: total assets 17,914,500 ≥ $10M), the M-1
// reference (never filed beside the M-3) and T-05's M-2 as drafted and with the proposed fix. The
// figures are T-06 §3 F2's and the T-05 capital seed's (seed/tax/ridgeline.ts CAPITAL_TOTAL): book
// income 1,256,200 reconciles to 1,250,000 through one permanent 6,200 tax-exempt interest row; M-2
// ends 6,860,000 against Schedule L 6,866,200 until line 4 carries the 6,200. tax-depth-booktax.
// foot.test.ts re-adds every row and line, so a changed figure fails there (ADR-050).
import type { TaxDepthScheduleOut, WorkbookM2Out } from "@abacus/api-client";

export type M2Variant = WorkbookM2Out["variant"];
/** e0 (TXP-04 a–c) and accepted (d: the fix approved in SHL-10 at 9:51 AM, Run 3 re-ran). */
export type BookTaxVariant = "e0" | "accepted";

export const M3: TaxDepthScheduleOut = {
  schedule: "m3",
  required: true,
  total_assets: "17914500",
  book_income: "1256200",
  filed: true,
  rows: [
    {
      line: "13",
      label: "Interest income (tax-exempt)",
      income_per_books: "6200",
      temporary: "0",
      permanent: "-6200",
      per_return: "0",
      note: "Form 8916-A attached",
    },
    {
      // No-difference lines collapse (T-06 §3 F2): one row carries them (1,256,200 − 6,200).
      line: "28",
      label: "Other items with no differences",
      income_per_books: "1250000",
      temporary: "0",
      permanent: "0",
      per_return: "1250000",
    },
    {
      line: "29",
      label: "Total income (loss) items",
      income_per_books: "1256200",
      temporary: "0",
      permanent: "-6200",
      per_return: "1250000",
    },
  ],
};

/** The M-1 reference (TXP-04 a′): under $50M an M-1 may replace M-3 Parts II–III; not filed. */
export const M1: TaxDepthScheduleOut = {
  schedule: "m1",
  required: false,
  total_assets: "17914500",
  book_income: "1256200",
  filed: false,
  rows: [
    {
      line: "1",
      label: "Net income (loss) per books",
      income_per_books: "1256200",
      temporary: "0",
      permanent: "0",
      per_return: "1256200",
    },
    {
      line: "6",
      label: "Income recorded on books this year not included on Schedule K (tax-exempt interest)",
      income_per_books: "6200",
      temporary: "0",
      permanent: "0",
      per_return: "6200",
    },
    {
      line: "9",
      label: "Income (loss) (Analysis of Net Income, line 1)",
      income_per_books: "1250000",
      temporary: "0",
      permanent: "0",
      per_return: "1250000",
    },
  ],
};

const LINES = {
  as_drafted: [
    [1, "Balance at beginning of year", "5960000"],
    [2, "Capital contributed: cash", "250000"],
    [3, "Net income (loss) (see instructions)", "1250000"],
    [4, "Other increases (itemize)", "0"],
    [5, "Add lines 1 through 4", "7460000"],
    [6, "Distributions: cash", "600000"],
    [8, "Add lines 6 and 7", "600000"],
    [9, "Balance at end of year. Subtract line 8 from line 5", "6860000"],
  ],
  with_fix: [
    [1, "Balance at beginning of year", "5960000"],
    [2, "Capital contributed: cash", "250000"],
    [3, "Net income (loss) (see instructions)", "1250000"],
    [4, "Other increases (itemize): tax-exempt interest", "6200"],
    [5, "Add lines 1 through 4", "7466200"],
    [6, "Distributions: cash", "600000"],
    [8, "Add lines 6 and 7", "600000"],
    [9, "Balance at end of year. Subtract line 8 from line 5", "6866200"],
  ],
} as const;

export const SCHEDULE_L_21 = "6866200";

export function m2(variant: M2Variant, state: BookTaxVariant = "e0"): WorkbookM2Out {
  // Accepted (d): the fix is the workbook's now, so "as drafted" is the fixed schedule.
  const fixed = variant === "with_fix" || state === "accepted";
  const lines = fixed ? LINES.with_fix : LINES.as_drafted;
  const ending = fixed ? "6866200" : "6860000";
  return {
    variant,
    beginning: "5960000",
    ending,
    tie: fixed ? "tie" : "off",
    difference: fixed ? "0" : "-6200",
    lines: lines.map(([line, label, amount]) => ({ line, label, amount })),
    item_l: {
      capital_ending: ending,
      m2_ending: SCHEDULE_L_21,
      tie: fixed ? "tie" : "off",
      difference: fixed ? "0" : "-6200",
    },
  };
}
