// EBP-05 (A-05-T44): Northwind's loans and distributions at Thu Sep 24, 2026, verbatim from the
// handoff spec, in T42's shapes. Figures foot: 288,500 + 96,200 - 57,450 - 14,850 = 312,400;
// 41 + 5 - 7 - 3 = 36; offsets 4,850 + 5,200 + 4,800 = 14,850. All names fictional. Dev and test
// only.

import type {
  LoanOffsetsOut,
  LoanRowOut,
  LoansOut,
  TestGridCellOut,
  TestGridOut,
} from "@abacus/api-client";

export const EBP05_WORK_ITEM = "6f1c2a90-0000-4000-8000-0000000000e5";
export type Ebp05Variant = "a" | "c";

function newLoan(
  key: string,
  name: string,
  on: string,
  loan: string,
  vested: string,
  limit: string,
  months: number,
  residence = false,
): LoanRowOut {
  return {
    id: `0a050000-0000-4000-8000-0000000000${key}`, participant_key: `NW-${key}`,
    participant_name: name, loan_ref: `L-${key}`, status: "new", originated_on: on,
    term_months: months, is_residence: residence, vested_balance: vested, new: loan,
    ending: loan, limit, within_limit: true,
  }; // prettier-ignore
}

export const NEW_LOANS: LoanRowOut[] = [
  newLoan("a1", "Tomás Ibarra", "2025-03-03", "15000.00", "41880.00", "20940.00", 60),
  newLoan("a2", "Rebecca Lindgren", "2025-04-22", "8000.00", "22400.00", "11200.00", 48),
  newLoan("a3", "Connor Gallagher", "2025-06-09", "25000.00", "96300.00", "48150.00", 60),
  newLoan("a4", "Chloe Dubois", "2025-08-18", "30000.00", "128400.00", "50000.00", 180, true),
  newLoan("a5", "Ethan Caldwell", "2025-11-03", "18200.00", "52000.00", "26000.00", 60),
];

export const OFFSETS: LoanOffsetsOut = {
  total: "14850.00",
  rows: [
    {
      loan_ref: "L-b1", participant_name: "Dmitri Volkov", terminated_on: "2025-02-14",
      offset_on: "2025-03-21", amount: "4850.00", form_1099r_code: "M1", reported_line: "2e(1)",
    },
    {
      loan_ref: "L-b2", participant_name: "Wallace Grant", terminated_on: "2025-05-09",
      offset_on: "2025-06-13", amount: "5200.00", form_1099r_code: "M1", reported_line: "2e(1)",
    },
    {
      loan_ref: "L-b3", participant_name: "Siobhan Kelly", terminated_on: "2025-09-19",
      offset_on: "2025-10-24", amount: "4800.00", form_1099r_code: "M1", reported_line: "2e(1)",
    },
  ],
}; // prettier-ignore

export function loansView(variant: Ebp05Variant): LoansOut {
  return {
    beginning: "288500.00", new: "96200.00", repayments: "57450.00", offsets: "14850.00",
    ending: "312400.00", foots: true, count_beginning: 41, count_new: 5, count_paid_off: 7,
    count_offset: 3, count_ending: 36, comparative_agrees: variant !== "c",
    comparative_off_by: variant === "c" ? "3200.00" : "0.00", part_iv_4b: "no", rows: NEW_LOANS,
    engine_version: "1", inputs_hash: "0".repeat(64),
  }; // prettier-ignore
}

interface Dist {
  name: string;
  type: string;
  amount: string;
  withholding: string;
  code: string;
}

const DISTRIBUTIONS: readonly Dist[] = [
  { name: "Corinne Blake", type: "Termination, direct rollover", amount: "84210.55", withholding: "0.00", code: "G" },
  { name: "Dmitri Volkov", type: "Termination, cash (+ offset $4,850.00)", amount: "12400.00", withholding: "3450.00", code: "1; M1" },
  { name: "Janelle Price", type: "Hardship, medical (safe-harbor event)", amount: "6500.00", withholding: "650.00", code: "1" },
  { name: "Arturo Mendez", type: "In-service, age 59½", amount: "30000.00", withholding: "6000.00", code: "7" },
  { name: "Siobhan Kelly", type: "Termination, direct rollover (+ offset $4,800.00)", amount: "152880.40", withholding: "0.00", code: "G; M1" },
  { name: "Graham Pierce", type: "Required minimum distribution", amount: "9812.33", withholding: "981.23", code: "7" },
  { name: "Noor Siddiqui", type: "Termination, cash", amount: "4250.00", withholding: "850.00", code: "1" },
  { name: "Tobias Lang", type: "Death, spouse beneficiary, cash", amount: "46300.00", withholding: "9260.00", code: "4" },
  { name: "Esther Kim", type: "Termination, direct rollover", amount: "61045.72", withholding: "0.00", code: "G" },
  { name: "Wallace Grant", type: "Termination, cash (+ offset $5,200.00)", amount: "18600.00", withholding: "4760.00", code: "1; M1" },
]; // prettier-ignore

function cell(key: string, value: string | null = null): TestGridCellOut {
  return { attribute_key: key, result: "agent_tested", by: "agent", citation_ids: [], value };
}

export function distributionsGrid(): TestGridOut {
  return {
    test_id: "0a050000-0000-4000-8000-0000000000d0",
    variant: "distribution",
    attributes: ["event", "consent", "vested", "amount", "withholding"],
    rows: DISTRIBUTIONS.map((d, i) => ({
      position: i + 1,
      item_id: `0a050000-0000-4000-8000-00000000${(256 + i).toString(16)}`,
      record_key: d.name,
      state: "agent_tested",
      detail: d.type,
      code: d.code,
      cells: [
        cell("event"),
        cell("consent"),
        cell("vested"),
        cell("amount", d.amount),
        cell("withholding", d.withholding),
      ],
    })),
    counts: { sample: 10, population: 64, exceptions: 0 },
    version_no: 1,
  };
}
