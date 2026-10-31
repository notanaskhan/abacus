// SHL-15's sheet in fixture mode (P-04-T54; the handoff's SHL-15 a–e and spec.md, verbatim): the
// rest of what the artboards draw beyond the C3 frames P-04-T34 seeded (seed/review.ts). Feld's
// four open issues in the queue's order (the 18A issue is "Issue 3 of 4"), the second Missing
// information issue that e's bulk instructions cover, b's and c's drafts as the artboards show
// them typed, the Northwind and Feld teams and Northwind's client contact. Ids are review.ts's
// where it has them; the rest are stable placeholders.

import type {
  AgentProposalOut,
  ClientContactOut,
  IssueCreateIn,
  IssueDetailOut,
  IssueItemOut,
  ListPageIssueItemOut,
  TeamRosterMemberOut,
} from "@abacus/api-client";
import {
  ANA,
  DANA,
  FELD_1040,
  HANNAH,
  KEVIN,
  MARCUS,
  SAMUEL,
  SHL15,
  id,
  issue18a,
  issueRow,
  k1,
  optOuts,
  row,
} from "./review";

const FELD_ENGAGEMENT = issueRow.engagement_id ?? id(251);
/** Northwind PY2025 EBP audit (b's record is its EBP-04 participant data workpaper). */
export const NORTHWIND_ENGAGEMENT = id(264);

const feld = (n: number, over: Partial<IssueItemOut>): IssueItemOut => ({
  ...issueRow,
  id: id(n),
  assignee_agent: false,
  instructions_required: false,
  link_count: 1,
  ...over,
});

/** Feld's four open issues, in the queue's order (TPL-09 Frame A under SHL-15 a and e). */
export const FELD_ISSUES: readonly IssueItemOut[] = [
  feld(208, { kind: "waiting_on_client", priority: "medium" }),
  feld(209, { kind: "missing_information", priority: "medium", assignee_agent: true }),
  issueRow,
  feld(210, { kind: "action_required", priority: "medium" }),
];
const TITLES: Readonly<Record<string, string>> = {
  [id(208)]: "Halvard consolidated 1099 is password-protected",
  [id(209)]: "2025 estimated payment confirmations are missing",
  [issueRow.id]: issue18a.title,
  [id(210)]: "Acknowledgment letters missing for gifts over $250",
};

export const feldPage = (items: readonly IssueItemOut[]): ListPageIssueItemOut => ({
  items: [...items],
  next_cursor: null,
  total: items.length,
  total_capped: false,
  counts: { open: items.length },
  facets: {},
});

/** Each Feld issue's detail (the three beyond the 18A issue carry no suggestion or run). */
export function feldDetail(issueId: string): IssueDetailOut | undefined {
  if (issueId === issueRow.id) return issue18a;
  const item = FELD_ISSUES.find((i) => i.id === issueId);
  if (item === undefined) return undefined;
  return {
    ...issue18a,
    issue: item,
    title: TITLES[issueId] ?? "",
    links: [],
    suggestion: null,
    explanations: [],
  };
}

/** e: the shared instruction for both Missing information issues, as the artboard shows it typed. */
export const BULK_TEXT =
  "Fill each missing value from its linked source and mark K-1 values as draft.\nDon't change taxable interest on line 2b (6,910).";
export const BULK_IDS: readonly string[] = [id(209), issueRow.id];

/** What a draft's linked chips read (an `IssueLinkIn` carries no label). */
export interface LinkChip {
  label: string;
  kind: "cell_range" | "form_field" | "file" | "request_item" | "finding";
}

export interface IssueDraft {
  create: IssueCreateIn;
  chips: readonly LinkChip[];
}

/** b: Ana Cruz's Waiting on client issue from EBP-04 F12:F15, typed as the artboard shows it. */
export const DRAFT_B: IssueDraft = {
  create: optOuts,
  chips: [
    { label: "EBP-04 Participant data!F12:F15", kind: "cell_range" },
    { label: "Northwind Census PY2025.xlsx", kind: "file" },
  ],
};

/** c: Samuel Ito's field flag on Ridgeline K-1 box 5 → Form 1040 line 2b (Review point). */
export const DRAFT_C: IssueDraft = {
  create: {
    record_type: "tax_return",
    record_id: FELD_1040,
    kind: "review_point",
    priority: "medium",
    title: "Confirm Ridgeline K-1 amounts against the final K-1 before export",
    assignee_user_id: KEVIN,
    assignee_agent: false,
    links: [
      { kind: "form_field", target_type: "tax_return", target_id: FELD_1040, anchor: "f1040.l2b" },
    ],
  },
  chips: [{ label: "Ridgeline K-1 box 5 → Form 1040 line 2b", kind: "form_field" }],
};

/** The created issues' details (b before the send; c's Review point). */
export const CREATED_B: IssueDetailOut = {
  ...SHL15.b,
  issue: { ...SHL15.b.issue, status: "open", version: 1 },
  request_item_id: null,
};
export const CREATED_C: IssueDetailOut = {
  ...issue18a,
  issue: {
    ...issueRow,
    id: id(211),
    kind: "review_point",
    priority: "medium",
    assignee_agent: false,
    assignee_user_id: KEVIN,
    assignee_name: "Kevin Osei",
    instructions_required: false,
  },
  title: DRAFT_C.create.title,
  links: [
    {
      kind: "form_field",
      label: "Form 1040 · line 2b",
      target_type: "tax_return",
      target_id: FELD_1040,
      anchor: "f1040.l2b",
    },
  ],
  suggestion: null,
  explanations: [],
};

export const NORTHWIND_TEAM: readonly TeamRosterMemberOut[] = [
  { user_id: ANA, display_name: "Ana Cruz", role: "staff" },
  { user_id: MARCUS, display_name: "Marcus Delaney", role: "senior" },
  { user_id: HANNAH, display_name: "Hannah Leclerc", role: "manager" },
];
export const FELD_TEAM: readonly TeamRosterMemberOut[] = [
  { user_id: KEVIN, display_name: "Kevin Osei", role: "staff" },
  { user_id: SAMUEL, display_name: "Samuel Ito", role: "manager" },
];
export const NORTHWIND_CONTACTS: readonly ClientContactOut[] = [
  {
    id: DANA,
    kind: "member",
    display_name: "Dana Kowalski",
    email: null,
    role: "Plan administrator",
    expires_at: null,
  },
];

export { FELD_ENGAGEMENT };

/** a″: the 18A fix's proposal as the artboard draws it: two values, proposed at 9:25 AM. */
export const FIX_18A_PROPOSAL: AgentProposalOut = {
  ...k1,
  title: "Fix: Source K-1 box 18A 'Tax-exempt interest'",
  proposed_at: "2026-09-14T14:25:00Z",
  change_count: 2,
  rows: [
    row(
      1,
      "f1040.l2a",
      "Form 1040 line 2a · Tax-exempt interest",
      null,
      "1,550",
      "K-1 box 18A",
      1,
    ),
    row(
      2,
      "it201.l20",
      "IT-201 line 20 · Interest on non-NY state and local obligations",
      null,
      "1,550",
      "K-1 statement p. 3",
      1,
    ),
  ],
  totals: [],
};
