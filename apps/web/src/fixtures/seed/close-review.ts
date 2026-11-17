// CLS-06 Close › Review (C-01-T39; handoff CLS-06): the review queue's detail, notes, the resolved
// Shopify duplicate, Ben Ashby's answer and Operating Checking ••4410's August register, verbatim
// from the handoff spec. 2 Medium + 5 Low = 7 = the Review badge; the 4 notes never count.
import type { CloseIssueOut, CloseIssuesOut, CloseRegisterOut } from "@abacus/api-client";
import { ISSUE_IDS, closePerson, copperleafIssues } from "./close-book";
import { stableId } from "./prng";

export type ReviewState = "a" | "a2" | "b" | "c" | "d" | "e" | "f" | "g";

/** The detail the queue's selected issue shows beyond the list row (fixture-only, C-01-T43). */
export interface IssueDetail {
  sub: string;
  assignee: "agent" | "RM" | "PR" | "client";
  account: string;
  why: string;
  question?: { text: string; meta: string };
  linked: { title: string; sub: string }[];
  registerLine?: string;
}

export const ASSIGNEES = [
  { value: "agent", label: "Accrued Agent" },
  { value: "RM", label: "Raj Malhotra" },
  { value: "PR", label: "Priya Raman" },
  { value: "client", label: "Client — Ben Ashby" },
] as const;

export const ISSUE_DETAIL: Record<string, IssueDetail> = {
  [ISSUE_IDS.soundElectric]: {
    sub: "Open · Waiting on client · Repairs & Maintenance",
    assignee: "agent",
    account: "Repairs & Maintenance",
    why: "Sound Electric Contractors was paid $3,200.00 on Aug 18 (check #2285) and the payment was coded to Repairs & Maintenance, which rose to $3,200 from $640 in July (+400%). The invoice is not in the binder. Electrical work above the $2,500 capitalization policy may be a betterment or restoration of the building's electrical system that must be capitalized (Treas. Reg. §1.263(a)-3). Ask the client what the work was and attach the invoice.",
    question: {
      text: "What was the $3,200 payment to Sound Electric?",
      meta: "Asked Ben Ashby · Sep 11 via portal · invoice requested · reminder Sep 15 · Ben replied 9:02 AM: answer coming this afternoon",
    },
    linked: [
      { title: "Operating Checking (Front Range Bank) ••4410", sub: "1 check · #2285" },
      {
        title: "Sound Electric Contractors, LLC",
        sub: "1099-NEC vendor · W-9 on file · paid $5,840.00 this year",
      },
      { title: "Sound Electric invoice — Aug 18 ($3,200)", sub: "Request · Requested Sep 11" },
    ],
    registerLine: "chk-2285",
  },
  [ISSUE_IDS.accruedExpenses]: {
    sub: "Open · Accrued Expenses",
    assignee: "RM",
    account: "Accrued Expenses",
    why: "",
    linked: [],
  },
  [ISSUE_IDS.check2281]: {
    sub: "Open · Operating Checking (Front Range Bank) ••4410",
    assignee: "RM",
    account: "Operating Checking (Front Range Bank) ••4410",
    why: "",
    linked: [],
  },
  [ISSUE_IDS.refund380]: {
    sub: "Open · Operating Checking ••4410",
    assignee: "RM",
    account: "Operating Checking ••4410",
    why: "",
    linked: [],
  },
  [ISSUE_IDS.prepaid]: {
    sub: "Open · Prepaid Insurance",
    assignee: "RM",
    account: "Prepaid Insurance",
    why: "",
    linked: [],
  },
  [ISSUE_IDS.payroll]: {
    sub: "Open · Payroll Expenses",
    assignee: "RM",
    account: "Payroll Expenses",
    why: "",
    linked: [],
  },
  [ISSUE_IDS.amexCycle]: {
    sub: "Open · Amex Business Card ••1009",
    assignee: "RM",
    account: "Amex Business Card ••1009",
    why: "",
    linked: [],
  },
}; // fmt: skip

/** c: Ben Ashby's reply (1:12 PM), its attachment and the agent's note (pre-fills Resolve). */
export const CLIENT_ANSWER = {
  reply:
    "Two breakers failed on Aug 14; Sound Electric replaced them and rewired the espresso bar circuit. The panel was not replaced and nothing new was added.",
  attachment: "SoundElectric_INV-SE-1187.pdf",
  agentNote:
    "Replacement of minor parts with no betterment, adaptation or restoration of the electrical system — a deductible repair; keep in Repairs & Maintenance.",
};

/** e: the four notes (evidence only; never counted in the badge). */
export const REVIEW_NOTES = [
  "Operating Checking ••4410 — opening balance agreed to the Jul 31 statement",
  "Checks #2287 and #2290 cleared Sep 2 and Sep 3 (bank feed)",
  "Square — 21 transfers agreed to bank deposits",
  "Payroll Checking ••4428 — clean tie-out, three pay dates funded",
];

/** f: the resolved Shopify duplicate (Show resolved). */
export const RESOLVED_SHOPIFY = {
  title: "Two Shopify 'Annual online store add-on' charges booked 2 days apart",
  meta: "Resolved by RM · Sep 8 · duplicate refunded Sep 4",
};

/** The queue as each state reads it: d resolves Sound Electric (badge 6), g is empty. */
export function copperleafReview(state: ReviewState = "a"): CloseIssuesOut {
  const base = copperleafIssues();
  if (state === "g") {
    return { ...base, open: 0, by_severity: { medium: 0, low: 0 }, items: [] };
  }
  const items: CloseIssueOut[] = base.items.map((i) =>
    i.issue_id === ISSUE_IDS.soundElectric
      ? {
          ...i,
          account_external_id: "35",
          register_line_ref: "chk-2285",
          why_surfaced: ISSUE_DETAIL[i.issue_id]?.why ?? null,
          ...(state === "d"
            ? {
                status: "resolved" as const,
                resolved_by: closePerson("PR"),
                waiting_on_client: false,
              }
            : {}),
        }
      : i.issue_id === ISSUE_IDS.check2281
        ? { ...i, account_external_id: "35" }
        : i,
  );
  const shopify: CloseIssueOut = {
    issue_id: stableId("issue:copperleaf:shopify-duplicate"),
    title: RESOLVED_SHOPIFY.title,
    severity: "low",
    issue_class: "recategorize",
    status: "resolved",
    resolved_by: closePerson("RM"),
    waiting_on_client: false,
  };
  const open = items.filter((i) => i.status === "open").length;
  return {
    ...base,
    open,
    by_severity: {
      medium: items.filter((i) => i.status === "open" && i.severity === "medium").length,
      low: items.filter((i) => i.status === "open" && i.severity === "low").length,
    },
    items: state === "f" ? [...items, shopify] : items,
  };
}

/** Operating Checking ••4410's August register (CLS-06 a; CLS-05 f), newest first. */
export function copperleafRegister4410(): CloseRegisterOut {
  type Row = [
    ref: string,
    date: string,
    type: string,
    category: string,
    payee: string | null,
    memo: string,
    amount: string,
  ];
  const rows: Row[] = [
    [
      "dep-0831",
      "2026-08-31",
      "Deposit",
      "Square Clearing",
      "Square, Inc.",
      "Square transfer — sales Aug 28–30",
      "6412.40",
    ],
    [
      "xfer-0831",
      "2026-08-31",
      "Transfer",
      "Payroll Checking ••4428",
      null,
      "Payroll funding — pay date Aug 31",
      "-24600.00",
    ],
    [
      "chk-2290",
      "2026-08-28",
      "Check #2290",
      "Utilities & Facilities",
      "Mile High Window Cleaning",
      "August service",
      "-802.33",
    ],
    [
      "dep-0828",
      "2026-08-28",
      "Deposit",
      "Square Clearing",
      "Square, Inc.",
      "Square transfer — sales Aug 27",
      "2356.11",
    ],
    [
      "dep-0827",
      "2026-08-27",
      "Deposit",
      "Square Clearing",
      "Square, Inc.",
      "Square transfer — sales Aug 26",
      "2131.10",
    ],
    [
      "chk-2287",
      "2026-08-26",
      "Check #2287",
      "Cost of Goods Sold — Packaging",
      "Denver Paper Supply",
      "Cups, bags and labels",
      "-3615.75",
    ],
    [
      "dep-0826",
      "2026-08-26",
      "Deposit",
      "Square Clearing",
      "Square, Inc.",
      "Square transfer — sales Aug 25",
      "2046.59",
    ],
    [
      "dep-0825",
      "2026-08-25",
      "Deposit",
      "Square Clearing",
      "Square, Inc.",
      "Square transfer — sales Aug 24",
      "2058.31",
    ],
    [
      "bp-0825",
      "2026-08-25",
      "Bill Payment",
      "Accounts Payable",
      "Rocky Ridge Dairy Co.",
      "Invoice RR-0811",
      "-2860.00",
    ],
    [
      "dep-0824",
      "2026-08-24",
      "Deposit",
      "Square Clearing",
      "Square, Inc.",
      "Square transfer — sales Aug 21–23",
      "7637.03",
    ],
    [
      "dep-0821",
      "2026-08-21",
      "Deposit",
      "Square Clearing",
      "Square, Inc.",
      "Square transfer — sales Aug 20",
      "2427.05",
    ],
    [
      "dep-0820s",
      "2026-08-20",
      "Deposit",
      "Shopify Clearing",
      "Shopify",
      "Shopify payout",
      "10284.60",
    ],
    [
      "dep-0820",
      "2026-08-20",
      "Deposit",
      "Square Clearing",
      "Square, Inc.",
      "Square transfer — sales Aug 19",
      "2170.20",
    ],
    [
      "dep-0819",
      "2026-08-19",
      "Deposit",
      "Square Clearing",
      "Square, Inc.",
      "Square transfer — sales Aug 18",
      "2250.15",
    ],
    [
      "chk-2285",
      "2026-08-18",
      "Check #2285",
      "Repairs & Maintenance",
      "Sound Electric Contractors, LLC",
      "Electrical work — espresso bar",
      "-3200.00",
    ],
    [
      "dep-0818",
      "2026-08-18",
      "Deposit",
      "Square Clearing",
      "Square, Inc.",
      "Square transfer — sales Aug 17",
      "2414.40",
    ],
    [
      "xfer-0817",
      "2026-08-17",
      "Transfer",
      "Payroll Checking ••4428",
      null,
      "Payroll funding — pay date Aug 17",
      "-24200.00",
    ],
    [
      "dep-0817",
      "2026-08-17",
      "Deposit",
      "Square Clearing",
      "Square, Inc.",
      "Square transfer — sales Aug 14–16",
      "7506.48",
    ],
  ]; // fmt: skip
  return {
    account_external_id: "35",
    next_cursor: null,
    items: rows.map(([line_ref, txn_date, txn_type, category, payee, memo, amount]) => ({
      line_ref,
      txn_date,
      txn_type,
      category,
      payee,
      memo,
      amount,
    })),
  };
}
