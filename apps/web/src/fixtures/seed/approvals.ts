// HOME-02 Approvals at E0 + 7 minutes (Mon Sep 14, 2026, 9:31 AM CT; I-01-T15; HOME-02 handoff):
// the evidence pane's basis table and calc card for Ridgeline's §754 decision (Pell Street
// Ventures' 5/35 sale to Pell Street II LLC on 6/30/2025), verbatim from the handoff and blueprint
// §9.8. Amounts are whole dollars. The queue rows themselves are seed/home.ts's (`homeGates`), so
// the HOME-01 badge, the band counts and this queue can never disagree.

export const APPROVALS_CLOCK = "2026-09-14T09:31:00-05:00";

export interface BasisRow {
  partner: string;
  taxCapital: number;
  liabilityShare: number;
  outsideBasis: number;
  insideShare: number;
}

export const BASIS_ROWS: readonly BasisRow[] = [
  {
    partner: "Ridgeline GP LLC",
    taxCapital: 93_124,
    liabilityShare: 220_966,
    outsideBasis: 314_090,
    insideShare: 314_090,
  },
  {
    partner: "Meera Shah",
    taxCapital: 2_529_356,
    liabilityShare: 4_198_354,
    outsideBasis: 6_727_710,
    insideShare: 6_727_710,
  },
  {
    partner: "Pell Street Ventures LLC",
    taxCapital: 1_996_860,
    liabilityShare: 3_314_490,
    outsideBasis: 5_311_350,
    insideShare: 5_311_350,
  },
  {
    partner: "Pell Street II LLC",
    taxCapital: 332_810,
    liabilityShare: 552_415,
    outsideBasis: 913_820,
    insideShare: 885_225,
  },
  {
    partner: "Jonah Feld",
    taxCapital: 1_914_050,
    liabilityShare: 2_762_075,
    outsideBasis: 4_676_125,
    insideShare: 4_676_125,
  },
];

/** The TOTAL row (blueprint §9.8). */
export const BASIS_TOTAL = {
  taxCapital: 6_866_200,
  liabilityShare: 11_048_300,
  outsideBasis: 17_943_095,
  insideShare: 17_914_500,
  difference: 28_595,
} as const;

/** The calc card: price paid less capital transferred (5/35 of 2,319,835). */
export const CALC_CARD = {
  purchasePrice: 360_000,
  transferredShare: [5, 35] as const,
  capitalAtSale: 2_319_835,
  capitalParts: [2_100_000, 218_750, 1_085] as const,
  capitalTransferred: 331_405,
  stepUp: 28_595,
  // Pell Street II's outside basis = price + income + tax-exempt − distributions + liabilities.
  outsideParts: {
    price: 360_000,
    income: 31_250,
    taxExempt: 155,
    distributions: 30_000,
    liabilities: 552_415,
  },
} as const;

/** "Waiting on you" bands for Daniel Reyes: 3 decisions + 6 sign-offs + 2 agent outputs. */
export const DANIEL_BANDS = { decisions: 3, sign_offs: 6, agent_outputs: 2 } as const;
