// AUD-27 fixtures (A-05-T57): verbatim from the handoff spec. Granite Peak's estimates and related
// parties (Simone Baptiste, Tue Oct 6, 2026 11:20 AM) and Northwind's parties in interest (Marcus
// Delaney, Sep 24). Every figure is what A-05-T53's engine returns for these inputs: 214,000 +
// 199,000 + 73,000 = 486,000 ties to TB 1450; 412,000 − 398,000 + 472,000 = 486,000; 412,000 vs
// 398,000 is over by 14,000 (3.4%); 84,000 vs 79,500 is over by 4,500 (5.4%).
import type { Aud27ItemOut, Aud27ListOut } from "@abacus/api-client";
import { stableId } from "./prng";

export const AUD27_WORK_ITEM = "6f1c2a90-0000-4000-8000-0000000000a7";
export const AUD27_EBP_WORK_ITEM = "6f1c2a90-0000-4000-8000-0000000000e7";
export const INVENTORY = stableId("estimate:granite:inventory-obsolescence");
export const PEAKLINE = stableId("related-party:granite:peakline-freight");
export const FINDING_F3 = stableId("finding:granite:f-3");

const INVENTORY_RESERVE: Aud27ItemOut = {
  id: INVENTORY,
  name: "Inventory obsolescence reserve",
  amount: "486000.00",
  status: "evaluated",
  pending_ep: true,
  account_ref: "1450",
  significant_risk: true,
  method_text: "Aging and discontinued-SKU percentages",
  disclosure_ref: "Note 4 Inventories — reserve method and amount",
  components: [
    { label: "Discontinued SKUs $214,000.00 × 100%", amount: "214000.00" },
    { label: "No sales > 365 days $398,000.00 × 50%", amount: "199000.00" },
    { label: "No sales 181–365 days $365,000.00 × 20%", amount: "73000.00" },
  ],
  method: { components_total: "486000.00", difference: "0.00", ties: true },
  rollforward: {
    opening: "412000.00",
    usage: "398000.00",
    additions: "472000.00",
    computed_closing: "486000.00",
    ties: true,
  },
  retrospectives: [
    {
      label: "FY2025",
      prior_estimate: "412000.00",
      outcome: "398000.00",
      difference: "14000.00",
      percent: "3.4",
      direction: "over",
    },
  ],
  range: { low: "451000.00", high: "512000.00", inside: true },
  bias: "none",
};

const WARRANTY: Aud27ItemOut = {
  id: stableId("estimate:granite:warranty"),
  name: "Warranty reserve",
  amount: "92000.00",
  status: "evaluated",
  pending_ep: false,
  significant_risk: false,
  method_text: "0.20% of warranty-eligible sales $46,000,000.00",
  retrospectives: [
    {
      label: "FY2025",
      prior_estimate: "84000.00",
      outcome: "79500.00",
      difference: "4500.00",
      percent: "5.4",
      direction: "over",
    },
  ],
  range: { low: "86000.00", high: "98000.00", inside: true },
  bias: "none",
};

const CREDIT_LOSSES: Aud27ItemOut = {
  id: stableId("estimate:granite:credit-losses"),
  name: "Allowance for credit losses",
  amount: "58000.00",
  status: "unevaluated",
  pending_ep: false,
  method_text: "Aging matrix (CECL)",
};

export function estimatesView(variant: "a" | "d" = "a"): Aud27ListOut {
  const items = [INVENTORY_RESERVE, WARRANTY, CREDIT_LOSSES];
  return {
    items:
      variant === "d"
        ? items.map((e) => ({ ...e, status: "unevaluated", pending_ep: false }))
        : items,
    allowed_actions: ["estimate.evaluate", "estimate.request_conclusion"],
  };
}

export function relatedPartiesView(variant: "b" | "e" = "b"): Aud27ListOut {
  return {
    items: [
      {
        id: stableId("related-party:granite:401k"),
        name: "Granite Peak Outdoor Supply 401(k) Plan",
        amount: null,
        status: "evaluated",
        pending_ep: false,
        source: "client_list",
        relationship: "Employee benefit plan sponsored by the company",
      },
      {
        id: stableId("related-party:granite:cfo"),
        name: "Luis Ferrante",
        amount: null,
        status: "evaluated",
        pending_ep: false,
        source: "client_list",
        relationship: "Chief financial officer (key management)",
      },
      {
        id: PEAKLINE,
        name: "Peakline Freight LLC",
        amount: null,
        status: "exception",
        pending_ep: false,
        source: "agent_search",
        relationship:
          "Candidate — remittance address matches the home address of a director in the Feb 12, 2026 board minutes",
        finding_id: variant === "e" ? FINDING_F3 : null,
      },
      {
        id: stableId("related-party:granite:front-range"),
        name: "Front Range Bank",
        amount: null,
        status: "screened_out",
        pending_ep: false,
        source: "agent_search",
        relationship: "Lender",
      },
    ],
    allowed_actions: ["related_party.manage", "related_party.screen_out"],
  };
}

export const PARTIES_IN_INTEREST: Aud27ListOut = {
  items: [
    [
      "Northwind Robotics, Inc.",
      "Plan sponsor and employer (§3(14)(C))",
      "Nonexempt (use of plan assets)",
      "Schedule H line 4a (not 4d)",
      "exception",
    ],
    ["Dana Kowalski", "Plan administrator, fiduciary (§3(14)(A))", null, null, "unevaluated"],
    ["Benefits committee", "Named fiduciary", null, null, "unevaluated"],
    [
      "Harborline Trust Company",
      "Directed trustee and custodian; Harborline Stable Value Fund",
      "§408(b)(8) / PTE 91-38",
      "4i asterisk",
      "unevaluated",
    ],
    [
      "Keystone Retirement Services",
      "Recordkeeper; KRS funds",
      "§408(b)(2)",
      "Schedule C",
      "unevaluated",
    ],
    ["Summit Plan Administrators", "TPA", "§408(b)(2)", "Schedule C", "unevaluated"],
    ["Brightwater Hale LLP", "Auditor", "§408(b)(2)", "Schedule C", "unevaluated"],
    [
      "Participants (employees of the sponsor, §3(14)(H))",
      "Participants",
      "§408(b)(1)",
      "4i asterisk",
      "unevaluated",
    ],
  ].map(([name, relationship, exemption, reporting, state]) => ({
    id: stableId(`party-in-interest:northwind:${String(name)}`),
    name: String(name),
    amount: null,
    status: state as Aud27ItemOut["status"],
    pending_ep: false,
    relationship: relationship ?? null,
    exemption: exemption ?? null,
    reporting: reporting ?? null,
  })),
  allowed_actions: ["party_in_interest.manage"],
  prohibited: [
    {
      late_remittance_id: stableId("late-remittance:northwind:dec-26"),
      principal: "33540.00",
      deposited_on: "2026-01-09",
      business_days_late: 10,
      lost_earnings: "64.38",
      correction_status: "pending_vfcp_scc",
      form_5330_status: "exposure",
    },
  ],
};
