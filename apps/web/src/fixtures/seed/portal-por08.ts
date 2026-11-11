// POR-08 · Approvals on fixtures (R-02-T19; docs/screens/POR-08.md): the handoff's figures for each
// artboard. a–d are Copperleaf's August 2026 close (non-attest; fixture-only until a provider
// registers `fs_package`, DV-08); e and e2 are Dana Kowalski's attest entries on Northwind's PY2025
// audit; f is Ben Ashby's September context with nothing waiting. Every amount is the handoff's
// (spec.md, AUD-16 and CLS-07); the arithmetic is footed in portal-por08.foot.test.ts.
import type { ApprovalItemDetailOut, ApprovalItemOut, ApprovalsOut } from "@abacus/api-client";
import { stableId } from "./prng";

export type Por08State = "a" | "a2" | "b" | "c" | "d" | "e" | "e2" | "f";

export const POR08_ID = {
  package: stableId("close-package:copperleaf-2026-08"),
  posted: [1, 2, 3, 4, 5, 6].map((n) => stableId(`posted-entry:copperleaf-2026-08-${String(n)}`)),
  aje1: stableId("proposed-entry:northwind-aje-1"),
  rje1: stableId("proposed-entry:northwind-rje-1"),
  paje1: stableId("proposed-entry:northwind-paje-1"),
  paje2: stableId("proposed-entry:northwind-paje-2"),
  uncorrected: stableId("uncorrected:northwind-py2025"),
} as const;

export const CONTEXT = {
  august: { key: "copperleaf-2026-08", label: "August 2026 Close" },
  september: { key: "copperleaf-2026-09", label: "September 2026 Close" },
  py2025: { key: "northwind-py2025", label: "PY2025 audit" },
} as const;

/** Copperleaf's six posted entries (QBO 48213–48218) and the 14,900 entry's lines. */
export const POSTED: readonly { title: string; amount: string; sub: string }[] = [
  {
    title: "Payroll accrual",
    amount: "11860.00",
    sub: "Wages for Aug 23–31, unpaid at month end · reverses Sep 1",
  },
  {
    title: "Prepaid insurance",
    amount: "700.00",
    sub: "Cedar Mutual business owner's policy, $8,400 ÷ 12",
  },
  {
    title: "Depreciation",
    amount: "2140.00",
    sub: "Equipment and café build-out · straight-line",
  },
  {
    title: "Deferred revenue (subscriptions)",
    amount: "5320.00",
    sub: "Coffee subscriptions earned in August",
  },
  {
    title: "Accrued expenses",
    amount: "14900.00",
    sub: "Coffee received Aug 28, August utilities and legal, not yet billed · reverses Sep 1",
  },
  {
    title: "Vendor refund — Rocky Ridge Dairy Co.",
    amount: "380.00",
    sub: "Refund on the Aug 27 Front Range Bank statement",
  },
];
export const ACCRUED_EXPENSE_LINES = [
  { account: "Inventory — Green Coffee", debit: "12600.00", credit: null },
  { account: "Utilities & Facilities", debit: "1480.00", credit: null },
  { account: "Legal & Professional Fees", debit: "820.00", credit: null },
  { account: "Accrued Expenses", debit: null, credit: "14900.00" },
] as const;

const PACKAGE_TITLE = "August 2026 financial statements";
const HIGHLIGHTS =
  "Revenue rose 4.5% to $214,600. Payroll rose 12.5% to $68,910: two baristas joined at the end of July, merit increases took effect Aug 1, and the roastery ran overtime during the Aug 10–14 changeover. Repairs and maintenance of $3,200 was an electrical repair at the espresso bar.";
const PARTS = [
  "Balance sheet",
  "Income statement",
  "Statement of cash flows",
  "AR & AP aging",
  "Commentary",
];

function item(over: Partial<ApprovalItemOut> & Pick<ApprovalItemOut, "id" | "kind" | "title">) {
  const base: ApprovalItemOut = {
    id: over.id,
    kind: over.kind,
    title: over.title,
    state: "waiting",
    amount: null,
    decided_by: null,
    decided_at: null,
    reason_code: null,
    question_sent_at: null,
    allowed_actions: ["ask"],
  };
  return { ...base, ...over };
}

function packageItem(state: Por08State): ApprovalItemOut {
  if (state === "b") {
    return item({
      id: POR08_ID.package,
      kind: "fs_package",
      title: PACKAGE_TITLE,
      state: "approved",
      decided_by: "Tess Moreno",
      decided_at: "2026-09-15T13:42:00Z",
    });
  }
  if (state === "c") {
    return item({
      id: POR08_ID.package,
      kind: "fs_package",
      title: PACKAGE_TITLE,
      state: "declined",
      decided_by: "Ben Ashby",
      decided_at: "2026-09-14T21:40:00Z",
      reason_code: "number_looks_wrong",
    });
  }
  return item({
    id: POR08_ID.package,
    kind: "fs_package",
    title: PACKAGE_TITLE,
    // Sep 14, 4:25 PM CT (the handoff's Card A sub-line).
    released_by: "Priya Raman",
    released_at: "2026-09-14T21:25:00Z",
    allowed_actions: ["approve", "decline", "ask"],
  });
}

export function postedItems(state: Por08State): ApprovalItemOut[] {
  return POSTED.map((p, i) =>
    item({
      id: POR08_ID.posted[i] ?? "",
      kind: "proposed_entry",
      title: p.title,
      state: "approved",
      amount: p.amount,
      question_sent_at: state === "d" && i === 4 ? "2026-09-14T21:41:00Z" : null,
    }),
  );
}

/** Frame e's four entries and frame e2's decisions (AUD-16's numbers). */
const ENTRIES = [
  {
    id: POR08_ID.aje1,
    title: "AJE-1 · Contributions receivable — December 26, 2025 payroll",
    amount: "48600.00",
    decided: "accepted",
    lines: [
      {
        account: "Employer and participant contributions receivable",
        debit: "48600.00",
        credit: null,
      },
      { account: "Participant contributions", debit: null, credit: "33540.00" },
      { account: "Employer contributions", debit: null, credit: "15060.00" },
    ],
    reason: null,
  },
  {
    id: POR08_ID.rje1,
    title: "RJE-1 · Loan offsets shown as benefits paid",
    amount: "14850.00",
    decided: "accepted",
    lines: [
      { account: "Benefits paid to participants", debit: "14850.00", credit: null },
      { account: "Deemed distributions of participant loans", debit: null, credit: "14850.00" },
    ],
    reason: null,
  },
  {
    id: POR08_ID.paje1,
    title: "PAJE-1 · Employer safe-harbor match on bonus pay (estimated)",
    amount: "35300.00",
    decided: "not_recorded",
    lines: [],
    reason: "Sponsor will correct under EPCRS in 2026",
  },
  {
    id: POR08_ID.paje2,
    title:
      "PAJE-2 · Accrued administrative expenses — Q4 recordkeeping $6,150, TPA $2,400, audit fee $4,500",
    amount: "13050.00",
    decided: "not_recorded",
    lines: [],
    reason: "Recorded when invoiced",
  },
] as const;

const SEP_25 = "2026-09-25T15:02:00Z";

function entryItems(state: Por08State): ApprovalItemOut[] {
  return ENTRIES.map((e) =>
    state === "e2"
      ? item({
          id: e.id,
          kind: "proposed_entry",
          title: e.title,
          amount: e.amount,
          state: e.decided,
          decided_by: "Dana Kowalski",
          decided_at: SEP_25,
        })
      : item({
          id: e.id,
          kind: "proposed_entry",
          title: e.title,
          amount: e.amount,
          allowed_actions: ["accept", "decline", "ask"],
        }),
  );
}

const UNCORRECTED = item({
  id: POR08_ID.uncorrected,
  kind: "uncorrected_misstatements",
  title: "Uncorrected misstatements",
  amount: "22250.00",
  allowed_actions: ["acknowledge", "ask"],
});

/** `GET /v1/portal/approvals` by artboard (no filter, or `filter=posted`). */
export function approvals(state: Por08State, filter: string | null): ApprovalsOut {
  if (state === "e" || state === "e2") {
    const items = state === "e2" ? [...entryItems(state), UNCORRECTED] : entryItems(state);
    const counts =
      state === "e2"
        ? { waiting: 1, posted: 0, approved: 2, declined: 2 }
        : { waiting: 4, posted: 0, approved: 0, declined: 0 };
    return {
      items: filter === "posted" ? [] : items,
      counts,
      contexts: [{ ...CONTEXT.py2025, state: "waiting" }],
    };
  }
  const contexts: ApprovalsOut["contexts"] = [
    { ...CONTEXT.august, state: packageItem(state).state },
    { ...CONTEXT.september, state: null },
  ];
  if (state === "f") {
    return {
      items: [],
      counts: { waiting: 0, posted: 0, approved: 0, declined: 0 },
      contexts: [
        { ...CONTEXT.september, state: null },
        { ...CONTEXT.august, state: "approved" },
      ],
    };
  }
  const pkg = packageItem(state);
  const counts = {
    waiting: pkg.state === "waiting" ? 1 : 0,
    posted: POSTED.length,
    approved: pkg.state === "approved" ? 1 : 0,
    declined: pkg.state === "declined" ? 1 : 0,
  };
  return { items: filter === "posted" ? postedItems(state) : [pkg], counts, contexts };
}

/** `GET /v1/portal/approvals/{kind}/{item_id}`. */
export function approvalDetail(state: Por08State, id: string): ApprovalItemDetailOut | undefined {
  const pkg = packageItem(state);
  if (id === pkg.id && state !== "e" && state !== "e2" && state !== "f") {
    return {
      ...pkg,
      seen_hash: "fixture-copperleaf-2026-08-v1",
      lines: [],
      parts: PARTS.map((label) => ({ label, deliverable_id: null })),
      support: [],
      legend: "Prepared by Brightwater Hale. No assurance is provided.",
      highlights: HIGHLIGHTS,
      reason: null,
    };
  }
  const posted = postedItems(state).find((p) => p.id === id);
  if (posted !== undefined) {
    const accrued = posted.id === POR08_ID.posted[4];
    return {
      ...posted,
      seen_hash: `fixture-${posted.id}`,
      lines: accrued ? [...ACCRUED_EXPENSE_LINES] : [],
      parts: [],
      support: accrued
        ? [
            { label: "Receiving log — Aug 28 (1,800 lb green coffee)", document_id: null },
            { label: "Utility bills — Sep 4", document_id: null },
            { label: "Hartwell & Lowe engagement letter", document_id: null },
          ]
        : [],
      legend: null,
      highlights: null,
      reason: null,
    };
  }
  const entry = ENTRIES.find((e) => e.id === id);
  const listed = entryItems(state).find((e) => e.id === id);
  if (entry !== undefined && listed !== undefined) {
    return {
      ...listed,
      seen_hash: `fixture-${entry.id}`,
      lines: [...entry.lines],
      parts: [],
      support: [],
      legend: null,
      highlights: null,
      reason: state === "e2" ? entry.reason : null,
    };
  }
  if (id === UNCORRECTED.id && state === "e2") {
    return {
      ...UNCORRECTED,
      seen_hash: "fixture-uncorrected-py2025",
      // The two entries not recorded: what they would add and take away (AUD-16's SUM).
      lines: [
        { account: "PAJE-1", debit: "35300.00", credit: null },
        { account: "PAJE-2", debit: null, credit: "13050.00" },
      ],
      parts: [],
      support: [],
      legend: null,
      highlights: null,
      reason: null,
    };
  }
  return undefined;
}
