// The trusts-and-estates fixture seed (T-07-T08; T-07 §5.3; SPEC-656 AC-15.6): the Calloway
// Family Trust's TY2025 allocation (TXT-03 a) and the Estate of Walter Thornbury's Form 706
// inventory and deductions (TXT-04 a, b), typed with the generated FW-1 and EW-1 types. The
// figures mirror `abacus_tools/synthetic/scenarios/brightwater_hale/fiduciary_slice.py`; the
// browser never sums them (the read model does), so the footing lives in `fiduciary.foot.test.ts`.
// The full read models per artboard arrive with each screen row (T-07-T15, T17, T25, T26).
import type { BeneficiaryRowOut, EstateAssetOut, EstateDeductionOut } from "@abacus/api-client";
import { stableId } from "./prng";

export const CALLOWAY_TRUST = "Calloway Family Trust";
export const THORNBURY_ESTATE = "Estate of Walter Thornbury";

export const FIDUCIARY_IDS = {
  callowayReturn: stableId("tax_return:calloway-family-trust:2025:1041"),
  thornburyReturn: stableId("tax_return:estate-of-walter-thornbury:2025:706"),
  nora: stableId("contact:nora-calloway"),
  theo: stableId("contact:theo-calloway"),
} as const;

export function callowayAllocation(): BeneficiaryRowOut[] {
  return [
    {
      contact_id: FIDUCIARY_IDS.nora,
      name: "Nora Calloway",
      payments: [
        { paid_on: "2025-06-30", amount: "80000.00" },
        { paid_on: "2025-12-15", amount: "80000.00" },
      ],
      distributions: "160000.00",
      share: "0.666667",
      dni_allocated: "160000.00",
      box_1: "40000.00",
      box_2a: "120000.00",
      box_2b: "96000.00",
      delivery: "portal_k1_recipient",
      package_id: stableId("k1_package:calloway:2025:nora"),
      package_status: "draft",
    },
    {
      contact_id: FIDUCIARY_IDS.theo,
      name: "Theo Calloway",
      payments: [{ paid_on: "2025-12-15", amount: "80000.00" }],
      distributions: "80000.00",
      share: "0.333333",
      dni_allocated: "80000.00",
      box_1: "20000.00",
      box_2a: "60000.00",
      box_2b: "48000.00",
      delivery: "portal_k1_recipient",
      package_id: stableId("k1_package:calloway:2025:theo"),
      package_status: "draft",
    },
  ];
}

export const CALLOWAY_DEDUCTION = "240000.00"; // Form 1041 line 18 (TXT-03 TIE-OUT)

type AssetRow = Pick<
  EstateAssetOut,
  | "schedule"
  | "description"
  | "dod_value"
  | "avd_value"
  | "basis_to_1041"
  | "basis_rule"
  | "status"
>;

const ASSETS: AssetRow[] = [
  {
    schedule: "A",
    description: "Residence",
    dod_value: "3850000.00",
    avd_value: "3790000.00",
    basis_to_1041: "3850000.00",
    basis_rule: "stepped_up",
    status: "valued",
  },
  {
    schedule: "B",
    description: "Harborline brokerage",
    dod_value: "8240000.00",
    avd_value: "7965000.00",
    basis_to_1041: "8240000.00",
    basis_rule: "stepped_up",
    status: "valued",
  },
  {
    schedule: "C",
    description: "Cash",
    dod_value: "412000.00",
    avd_value: "412000.00",
    basis_to_1041: "412000.00",
    basis_rule: "stepped_up",
    status: "valued",
  },
  {
    schedule: "D",
    description: "Life insurance (Form 712 requested)",
    dod_value: "1000000.00",
    avd_value: "1000000.00",
    basis_to_1041: null,
    basis_rule: "non_probate_excluded",
    status: "gathering_support",
  },
  {
    schedule: "F",
    description: "Tangible personal property",
    dod_value: "186000.00",
    avd_value: "186000.00",
    basis_to_1041: "186000.00",
    basis_rule: "stepped_up",
    status: "gathering_support",
  },
  {
    schedule: "I",
    description: "IRA (IRD; no step-up)",
    dod_value: "2712000.00",
    avd_value: "2640000.00",
    basis_to_1041: null,
    basis_rule: "ird_no_step_up",
    status: "valued",
  },
];

export function thornburyInventory(): EstateAssetOut[] {
  return ASSETS.map((row) => ({
    ...row,
    id: stableId(`estate_asset:thornbury:${row.schedule}`),
    support_text: null,
    request_item_id: null,
    citation_ids: [],
    version: 1,
  }));
}

export function thornburyDeductions(): EstateDeductionOut[] {
  const rows: [EstateDeductionOut["schedule"], string, string, EstateDeductionOut["election"]][] =
    [
      ["J_funeral", "Funeral expenses", "28500.00", "none"],
      ["J_administration", "Administration expenses", "240000.00", "s642g_pending"],
      ["K", "Debts of the decedent", "131500.00", "none"],
      ["O", "Charitable bequests", "500000.00", "none"],
    ];
  return rows.map(([schedule, description, amount, election]) => ({
    id: stableId(`estate_deduction:thornbury:${schedule}`),
    schedule,
    description,
    amount,
    estimated: false,
    election,
    citation_ids: [],
    version: 1,
  }));
}
