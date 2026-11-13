// TXP-05 · Review › Schedule K words (T-05-T43; handoff TXP-05 spec.md; docs/screens/TXP-05.md).
// Verbatim from the handoff; the strings marked undesigned are T-05-T03's.

export const COPY = {
  views: "Schedule K view",
  federal: "Federal",
  state: "State K-1 amounts",
  title: "Schedule K",
  allocation: "Allocation Structure…",
  formPreview: "Form preview",
  tally: "Schedule K checks",
  pane: "Partners' distributive share items — Schedule K and K-1 matrix",
  draft: "Draft K-1 · pre-release",
  table: "Schedule K and K-1 matrix",
  building: "Workbook agent is drafting the K-1s",
  pending: "Pending",
  stmt: "stmt",
  footnote:
    "Pell Street Ventures LLC: 35% × first-half items + 30% × second-half items (§706(d) interim closing, monthly convention). Pell Street II LLC: 5% × second-half items only.",
  columns: { line: "Line", item: "Item", total: "Schedule K", sum: "Σ K-1s", tie: "Tie" },
  groups: {
    income: "INCOME (LOSS)",
    other: "OTHER INFORMATION",
    analysis: "ANALYSIS OF NET INCOME",
    items: "K-1 ITEMS J · K · L",
    states: "STATE K-1 AMOUNTS",
  },
  rows: {
    analysis: "Net income (loss): lines 1–11 less 12–13e and 21",
    qbi: "Other items — §199A statement (QBI = line 2 share; UBIA of qualified property 15,752,000 shared by year-end %)",
    itemJ: "Profit / loss / capital % — beginning → ending",
    itemK: "Share of liabilities at 12/31 — qualified nonrecourse + nonrecourse",
    itemL: "Ending capital (tax basis) — as drafted",
    itemLFixed: "Ending capital (tax basis)",
    schL: "(Sch. L)",
  },
  cards: {
    sumK1: "Schedule K = Σ K-1s",
    count: "K-1 count = Item I",
    analysis: "Analysis of net income",
    itemK: "Item K = Sch. L liabilities",
    itemL: "Item L = Sch. L capital",
    allocation: "Allocation",
  },
  allocationTag: {
    straight_percentage: "Straight percentage",
    targeted_waterfall: "Targeted waterfall",
  },
  allocationStatus: {
    approved: "Approved",
    pending_approval: "Pending approval",
    editing: "Editing",
    superseded: "Superseded",
  },
  breakdown: "Form 8825 → line 2",
  itemLOff: "Item L is off",
  openCapital: "Capital Accounts",
  openIssues: "Issues",
  partnerMenu: "Partner",
  k1Package: "K-1 package",
  /** Undesigned (T-05-T03): TAX-11 is T-06's (planned link). */
  k1Page: "K-1 page in Form preview (planned)",
  partners: "Partners",
} as const;

/** Header tags (GP or LP) by the partner's kind; Pell Street II's period note is the handoff's. */
export const PARTNER_NOTE: Readonly<Record<string, string>> = {
  "Pell Street II LLC": "7/1–12/31",
};
