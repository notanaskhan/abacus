// CLS-09 Close plan editor copy (C-01-T36): verbatim from the handoff's spec.md and screenshots
// (CLS-09 a to f). Templates in braces are filled by `fill` in the screen.
import type { PlanRowOut } from "@abacus/api-client";

export const COPY = {
  closePlan: "Close plan",
  back: "Back",
  tabs: { plan: "Plan", requests: "Requests", history: "History" },
  byClass: "By class",
  byProcedure: "By procedure",
  published: "Published {date} by {name}",
  draftTitle: "Draft v{version}",
  draftChanges: "Draft v{version} · {changes}",
  oneChange: "1 change",
  manyChanges: "{n} changes",
  agentDraftTitle: "Draft v{version} · Close Planner",
  agentDraftMeta: "Drafting · {date} · requested by {name}",
  planTitle: "Close plan v{version}",
  editPlan: "Edit plan",
  publish: "Publish v{version}",
  requestPublish: "Request publish…",
  publishTitle: "Publish v{version}?",
  publishBody: "It applies from the {next} close; {current} stays on v{previous}.",
  tally: {
    accounts: "Accounts",
    procedures: "Procedures",
    requests: "Client requests",
    requestsValue: "{n} / month",
    manager: "Manager review",
    senior: "Senior review",
    ajePolicy: "AJE policy",
  },
  /** S48 rest (DV-a): the control bar's Tag 23h ("Template · Café with Square/Shopify"). */
  template: "Template · {name}",
  /** The ⇕ after "v3" in the close header (the version stepper). */
  versionStepper: "Versions",
  search: "Search accounts",
  procedures: "Procedures",
  addProcedure: "Add procedure",
  columns: {
    account: "Account",
    procedure: "Procedure",
    method: "Method",
    evidence: "Evidence required",
    source: "Source",
    review: "Review",
    frequency: "Frequency",
    threshold: "Threshold",
  },
  changed: "Changed",
  drafting:
    "Close Planner is drafting from 14 months of QuickBooks Online history · {done} of {total} accounts",
  adopt: "Adopt {account}",
  footnote:
    "Equity is reviewed at year end and handed to tax in CLS-12; it is not part of the 21.",
  drawer: {
    evidence: "Evidence required",
    review: "Review",
    frequency: "Frequency",
    threshold: "Threshold",
    source: "Source",
  },
  empty: {
    title: "No close plan yet",
    body: "Start from a template, or let the Close Planner draft one from the client’s ledger history. A Manager or Partner publishes it.",
    draftFromHistory: "Draft from ledger history",
  },
  requests: {
    title: "Requests",
    due: "BD {n}",
  },
  history: { title: "History" },
  noThreshold: "—",
} as const;

export const PROCEDURE: Record<PlanRowOut["procedure"], string> = {
  reconciliation: "Reconciliation",
  aging: "Aging",
  clear_and_age: "Clear & age",
  third_party_sales: "Third-party sales",
  rollforward: "Rollforward",
  amortization: "Amortization",
  depreciation: "Depreciation",
  aging_cutoff: "Aging & cutoff",
  // eslint-disable-next-line no-restricted-syntax -- the accounting procedure (C-01 §3 F2; handoff CLS-09), not the product name
  accrual: "Accrual",
  tie_to_return: "Tie to return",
  tie_to_filings: "Tie to filings",
  recategorize: "Recategorize",
  flux: "Flux",
};

export const SOURCE: Record<PlanRowOut["source"], string> = {
  bank_feed: "Bank feed",
  client_upload: "Client upload",
  quickbooks_online: "QuickBooks Online",
  files: "Files (on file)",
  accrued_register: "Accrued register",
};

export const REVIEW: Record<PlanRowOut["review_level"], string> = {
  senior_signoff: "Senior sign-off",
  manager_approval: "Manager approval",
};

export const FREQUENCY: Record<PlanRowOut["frequency"], string> = {
  monthly: "Monthly",
  quarterly: "Quarterly",
  annual: "Annual",
};

export function fill(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? `{${k}}`));
}
