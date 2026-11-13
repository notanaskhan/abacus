// TXP-06 · Allocation Structure (modal sheet) words (T-05-T44; handoff TXP-06 spec.md;
// docs/screens/TXP-06.md). Verbatim from the handoff; the strings marked undesigned are
// T-05-T03's.

export const COPY = {
  title: "Allocation Structure",
  approve: "Approve structure",
  approved: (by: string, on: string) => `Approved · ${by} · ${on}`,
  summary: "Summary",
  kv: {
    structure: "Structure",
    income: "Income to allocate",
    distributable: "Distributable",
    method: "Method",
  },
  kind: { straight_percentage: "Straight percentage", targeted_waterfall: "Targeted waterfall" },
  method: {
    straight: "Interim closing, monthly convention",
    proration: "Proration, calendar-day convention",
    waterfall: "Target capital account allocation",
  },
  convention: { calendar_day: "calendar-day", semi_monthly: "semi-monthly", monthly: "monthly" },
  noWaterfall: "— (no liquidation waterfall)",
  reconciliation: "Reconciliation",
  partners: "Partners",
  roles: {
    gp: "General partner",
    lp: "Limited partner",
    member: "Member",
    shareholder: "Shareholder",
  },
  tags: { gp: "GP", lp: "LP", member: "LP", shareholder: "LP" },
  rules: "Allocation rules",
  waterfall: "Distribution waterfall",
  priority: (n: number) => `Priority ${String(n)}`,
  available: "Available to rung",
  priorTiers: "Prior tiers",
  remaining: "Remaining after rung",
  byPeriod: "Allocation by period",
  cumulative: "Cumulative liquidation",
  reconPeriods: "Allocation reconciliation",
  backSolve: "Back-solve reconciliation",
  partner: "Partner",
  total: "Total",
  begin: "Begin",
  target: "Target",
  plug: "Plug",
  pending: "Pending",
  reasoning: "Reasoning",
  citations: (n: number) => `${String(n)} citations`,
  save: "Save",
  cancel: "Cancel",
  edit: "Edit rung",
  /** Undesigned (T-05-T03): the inline editor's field names. */
  fields: { rate: "Rate %", target: "Target %", gp: "GP %" },
  gpShare: (pct: string) => `GP share of profit = ${pct}% ✓`,
  checks: {
    straight: ["Allocations to Schedule K", "Periods sum to the year", "Item L rollforward"],
    waterfall: ["Waterfall to target capital", "K-1 income", "Item L rollforward"],
  },
  ridgeline: {
    summary:
      "Every item is allocated by percentage interest. The 6/30/2025 transfer splits the year into two periods; each earns half of every item (§706(d) interim closing, monthly convention).",
    incomeSub: "rental 1,231,600 · interest 18,400 · tax-exempt 6,200",
    rung1: "Pro rata by percentage interest",
    rung1Sub: "Per partnership agreement §4.1; transfer of 6/30/2025 per assignment agreement",
    rung2: "Special allocations",
    rung2Sub: "None in the agreement · §704(c): no contributed property",
    reasoning:
      "Read from the Agreement of Limited Partnership §4.1 (allocations follow Percentage Interests) and the 6/30/2025 Assignment §3 (closing of the books at the transfer date)",
  },
  harborview: {
    summary:
      "Book income back-solves to each partner's target capital through the liquidation waterfall.",
    rungs: {
      return_of_capital: [
        "Return of Capital",
        "Each partner recovers contributed capital before any profit is shared",
      ],
      preferred_return: [
        "{pct}% Preferred Return",
        "{pct}% simple return on unreturned LP capital for the year",
      ],
      catch_up: [
        "100% GP Catch-up to {pct}%",
        "The general partner takes 100% until it holds {pct}% of profit distributed so far",
      ],
      promote: [
        "Promote + Residual",
        "{pct}% GP promote, {lp}% to LPs pro rata by contributed capital",
      ],
    },
  },
  periodLabel: (from: string, to: string, amount: string) => `${from}–${to} · ${amount}`,
  tooltip: (name: string, amount: string, pct: string, of: string) =>
    `${name} · ${amount} · ${pct}% of ${of}`,
} as const;
