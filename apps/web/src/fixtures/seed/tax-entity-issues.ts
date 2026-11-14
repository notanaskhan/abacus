// TXP-10's reads in fixture mode (T-05-T58; handoff TXP-10 spec.md verbatim): Ridgeline's 11 open
// issues (5 waiting on the client + 6 review points), the selected review point's detail with its
// proposed fix (A, A2), the §754 waiting item's client request (B), the agent fixing (C) and the
// resolved state with the badge at 10 (D). Nothing is computed here.
import type {
  IssueDetailOut,
  WorkbookIssueAssigneesOut,
  WorkbookReturnIssueOut,
  WorkbookReturnIssuesOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export type IssuesState = "a" | "b" | "c" | "d" | "f";

const iss = (key: string) => stableId(`issue:ridgeline:${key}`);
export const TAX_EXEMPT = iss("tax-exempt-interest");
export const ELECTION_754 = iss("754-election");
const AGENT = { kind: "agent" as const, user_id: null, name: "Accrued Agent" };

function row(
  key: string,
  title: string,
  section: "waiting_on_client" | "review_points",
  step: string,
  extra: Partial<WorkbookReturnIssueOut> = {},
): WorkbookReturnIssueOut {
  return {
    id: iss(key),
    title,
    section,
    step,
    status: "open",
    kind: section === "waiting_on_client" ? "waiting_on_client" : "review_point",
    priority: "medium",
    blocks: ["final_approval"],
    cells: [],
    version: 1,
    allowed_actions: ["issue.resolve", "issue.assign"],
    ...extra,
  };
}

const ROWS: readonly WorkbookReturnIssueOut[] = [
  row("754-election", "§754 election: partners' decision and support for Pell Street II's $360,000 purchase price", "waiting_on_client", "§706(d) interim closing · sent to Owen Calder Sep 11", {
    // T-05-T51 (stands as designed): a client contact is reached by sending to the client, not
    // as an assignee; the request is the client's.
    request_item_id: stableId("request-item:ridgeline:754"),
    cells: [
      { sheet: "04 Partner Txns", range: "D14" },
      { sheet: "04 Partner Txns", range: "E14" },
      { sheet: "09 K-1s", range: "F11" },
    ],
  }),
  row("pell-street-transfer", "Pell Street transfer (6/30/2025): assignment agreement and transfer-date balances", "waiting_on_client", "§706(d) interim closing · sent Sep 11"),
  row("elm-street-roof", "Elm Street roof replacement: contractor invoice and placed-in-service date", "waiting_on_client", "Depreciation register · sent Sep 10"),
  row("bergen-street-deposits", "Bergen Street tenant security deposit ledger supporting 121,800", "waiting_on_client", "Line mapping · sent Sep 10"),
  row("december-re-tax", "December real estate tax installment: county bill supporting the 18,500 accrual", "waiting_on_client", "Import trial balance · sent Sep 10"),
  row("tax-exempt-interest", "Tax-exempt interest 6,200 omitted from the capital rollforward", "review_points", "Capital accounts & Schedule M-2 · 4 days", {
    assignee: AGENT,
    allowed_actions: ["issue.resolve", "issue.assign", "issue.fix"],
    cells: [
      { sheet: "05 Capital", range: "H8" },
      { sheet: "05 Capital", range: "H9" },
      { sheet: "05 Capital", range: "H10" },
      { sheet: "05 Capital", range: "H11" },
      { sheet: "05 Capital", range: "H12" },
      { sheet: "06 Schedule K", range: "C31" },
      { sheet: "07 M-2", range: "C9" },
    ],
  }),
  row("larimer-bonus", "Larimer parking lot: 100% bonus requires acquisition after Jan 19, 2025", "review_points", "Bonus eligibility"),
  row("743b-placeholder", "§743(b) placeholder 28,595 pending the §754 decision", "review_points", "§706(d) interim closing"),
  row("apportionment", "Apportionment by property: IL 46.0% · CO 31.5% · NY 22.5%", "review_points", "Apportionment & PTET"),
  row("nonrecourse-752", "Nonrecourse mortgage shared by year-end profit percentages under §752", "review_points", "Federal K-1s (5)"),
  row("k2-k3", "Schedules K-2/K-3 required — domestic filing exception unavailable", "review_points", "State K-1s & K-3s · Sep 10"),
];

export function ridgelineIssues(state: IssuesState, showResolved = false): WorkbookReturnIssuesOut {
  const resolved = state === "d" || state === "f";
  const items = ROWS.map((r) => {
    if (r.id !== TAX_EXEMPT) return r;
    if (state === "c") return { ...r, status: "in_progress" };
    if (resolved) return { ...r, status: "resolved", version: 3 };
    return r;
  }).filter((r) => (state === "f" ? r.status !== "open" : true));
  const open = items.filter((r) => ["open", "in_progress", "reopened"].includes(r.status));
  const count = (k: string) => open.filter((r) => r.section === k).length;
  return {
    items: showResolved ? items : open,
    by_section: { waiting_on_client: count("waiting_on_client"), review_points: count("review_points") },
    by_step: {},
    open_total: open.length,
    resolved_total: items.length - open.length,
    sections: [
      { key: "waiting_on_client", title: "Waiting on the client", count: count("waiting_on_client") },
      { key: "review_points", title: "Review points", count: count("review_points") },
    ],
  };
}

const item = (id: string, kind: "review_point" | "waiting_on_client", status: string) => ({
  id,
  kind,
  status,
  priority: "medium",
  version: 1,
  allowed_actions: [],
  assignee_agent: kind === "review_point",
  assignee_name: null,
  assignee_user_id: null,
  blocks: ["final_approval"],
  created_at: "2026-09-10T21:09:00Z",
  engagement_id: null,
  instructions_required: false,
  link_count: 0,
  record: { type: "tax_return", id: stableId("work-item:ridgeline-2025-1065") },
  work_item_id: stableId("work-item:ridgeline-2025-1065"),
});

export function issueDetail(id: string, state: IssuesState): IssueDetailOut {
  const waiting = id === ELECTION_754;
  const status = waiting ? "open" : state === "c" ? "in_progress" : state === "d" ? "resolved" : "open";
  return {
    title: ROWS.find((r) => r.id === id)?.title ?? "",
    record_label: "Ridgeline Property Partners, LP · 2025 Form 1065",
    issue: item(id, waiting ? "waiting_on_client" : "review_point", status) as unknown as IssueDetailOut["issue"],
    internal_note: waiting
      ? "Pell Street II LLC paid $360,000 for 5 points carrying 331,405 of capital (5/35 of Pell Street Ventures' 6/30 capital of 2,319,835). Without the partners' decision, the 28,595 §743(b) adjustment cannot be computed or allocated under §755, and the §754 statement must be attached to the timely filed return due Sep 15, 2026."
      : "Schedule M-2 and every partner's Item L sum to 6,860,000, but Schedule L line 21 shows partners' capital of 6,866,200. Tax-exempt interest of 6,200 from the municipal bond fund (Schedule K line 18a) is allocated on the K-1s but missing from 'Other increases'. Final approval and K-1 release are blocked until M-2 ties.",
    client_wording: waiting
      ? "Ridgeline 2025 · §754 decision — please confirm whether the partnership will make a §754 election"
      : null,
    client_contact: waiting ? { contact_id: stableId("contact:owen-calder"), name: "Owen Calder", role_label: "Client" } : null,
    request_item_id: waiting ? stableId("request-item:ridgeline:754") : null,
    links: [],
    events:
      state === "d" && !waiting
        ? [{ actor_kind: "human", actor_name: "Samuel Ito", actor_user_id: stableId("user:samuel-ito"), at: "2026-09-14T14:52:00Z", event: "resolved" }]
        : [],
    explanations: waiting
      ? []
      : [{
          id: stableId("explanation:ridgeline:m2"), agent_run_id: stableId("run:ridgeline:2"), citations: [],
          explained_at: "2026-09-10T21:09:00Z", pinned: false,
          text: "The capital tie-out compares M-2 line 9 with Schedule L line 21 after every run. The 6,200 difference equals Schedule K line 18a exactly, and line 4 is blank.",
        }],
    fix_instructions: null,
    fix_run: waiting
      ? null
      : {
          agent_run_id: stableId("run:ridgeline:fix"),
          label: "Writing 05 Capital!H8:H12 and 07 M-2!C9",
          proposal_id: state === "c" || state === "d" ? null : stableId("proposal:ridgeline:m2-fix"),
          status: state === "c" ? "running" : "succeeded",
        },
    suggestion: null,
  } as unknown as IssueDetailOut;
}

export const ASSIGNEES: WorkbookIssueAssigneesOut = {
  items: [
    { kind: "person", id: stableId("user:olivia-brandt"), name: "Olivia Brandt", detail: "Preparer" },
    { kind: "person", id: stableId("user:samuel-ito"), name: "Samuel Ito", detail: "Reviewer" },
    { kind: "agent", id: null, name: "Accrued Agent", detail: null },
    { kind: "client_contact", id: stableId("contact:owen-calder"), name: "Owen Calder", detail: "Client" },
  ],
};
