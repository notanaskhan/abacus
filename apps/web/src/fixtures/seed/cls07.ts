// CLS-07 fixture reads (C-02-T17, DEC-5637): Copperleaf Coffee Roasters, Inc.'s August 2026
// proposed entries per artboard, built from the Python scenario's export
// (`scenario.cls07-entries.json`, `make fixtures`; no row is typed here). Each state sets the
// entries' statuses the way the C8 routes would leave them; tallies are code's, counted from the
// rows, the way `close_approvals.close_entries` counts them.
import type {
  EntryOut,
  PostingCloseEntriesOut,
  PostingCloseEntryRowOut,
  ProposedEntryStatus,
} from "@abacus/api-client";
import { stableId } from "./prng";
import exported from "./scenario.cls07-entries.json";

export type Cls07Fixture = "a" | "a2" | "b" | "c" | "c2" | "d" | "e" | "f" | "g";

interface Exported {
  ref: string;
  title: string;
  account_class: string | null;
  class_limit: string | null;
  line_count: number;
  amount: string;
  initial: string;
  reverses_on: string | null;
  qbo_id: string;
  lines: readonly { account: string; debit: string; credit: string }[];
}

const ENTRIES: readonly Exported[] = exported.entries;
export const POLICY = exported.policy;
export const CLOSE_WORK_ITEM_ID = stableId("work-item:copperleaf-close-2026-08");
/** The batch approval's minute (CLS-07 b) and the held entry's (CLS-07 c). */
const BATCH_AT = "9:31 AM";
const HELD_AT = "10:12 AM";
const POSTED_BATCH = "2026-08-A";
const BATCH_ID = stableId("posting-batch:2026-08-A");
const FAILED_REF = "AJE-03"; // CLS-07e: "Accumulated Depreciation" inactive in QuickBooks

const PEOPLE = {
  "raj-malhotra": { name: "Raj Malhotra", initials: "RM", role: "Senior" },
  "priya-raman": { name: "Priya Raman", initials: "PR", role: "Partner" },
} as const;
type Persona = keyof typeof PEOPLE;

function entryId(ref: string): string {
  return stableId(`proposed-entry:copperleaf-2026-08:${ref}`);
}

function cents(v: string): number {
  const [whole = "0", frac = "00"] = v.split(".");
  return Number(whole) * 100 + Number(frac.padEnd(2, "0"));
}

function dollars(c: number): string {
  return `${String(Math.trunc(c / 100))}.${String(c % 100).padStart(2, "0")}`;
}

interface Row {
  e: Exported;
  status: ProposedEntryStatus;
  label: string | null;
}

function rowsOf(state: Cls07Fixture): Row[] {
  const six = state === "c" || state === "c2" || state === "d" || state === "e";
  const entries = six ? ENTRIES : ENTRIES.slice(0, 5);
  const batch = `Approved by RM under ${POLICY} · ${BATCH_AT}`;
  const held = `Approved by PR · ${HELD_AT}`;
  return entries.map((e): Row => {
    const within = e.initial === "within_threshold";
    switch (state) {
      case "a":
      case "a2":
      case "g":
        return {
          e,
          status: state === "g" ? "review_required" : (e.initial as ProposedEntryStatus),
          label: null,
        };
      case "f":
        // DEC-53 / ADR-187: the policy-acceptance frame is fixture-only, never live.
        return within
          ? { e, status: "approved", label: `Accepted by Policy · ${POLICY}` }
          : { e, status: "review_required", label: null };
      case "b":
        return within
          ? { e, status: "approved", label: batch }
          : { e, status: "review_required", label: null };
      case "c":
        return within
          ? { e, status: "approved", label: batch }
          : { e, status: "review_required", label: null };
      case "c2":
        return { e, status: "approved", label: within ? batch : held };
      case "d":
        return { e, status: "posted", label: within ? batch : held };
      case "e":
        return {
          e,
          status: e.ref === FAILED_REF ? "failed_post" : "posted",
          label: within ? batch : held,
        };
    }
  });
}

function personaOf(state: Cls07Fixture): Persona {
  return state === "c" || state === "c2" || state === "d" ? "priya-raman" : "raj-malhotra";
}

function allowed(
  row: Row,
  persona: Persona,
): NonNullable<PostingCloseEntryRowOut["allowed_actions"]> {
  if (row.status === "within_threshold")
    return ["proposed_entry.approve", "proposed_entry.reject_close"];
  if (row.status === "review_required") {
    return persona === "priya-raman"
      ? ["proposed_entry.approve", "proposed_entry.reject_close"]
      : ["proposed_entry.request_approval", "proposed_entry.reject_close"];
  }
  if (row.status === "approved") return ["proposed_entry.withdraw_approval", "posting_batch.post"];
  if (row.status === "failed_post") return ["posting_batch.post"];
  return [];
}

function tally(rows: readonly Row[]) {
  return { count: rows.length, amount: dollars(rows.reduce((n, r) => n + cents(r.e.amount), 0)) };
}

export function closeEntries(state: Cls07Fixture): PostingCloseEntriesOut {
  const rows = rowsOf(state);
  const persona = personaOf(state);
  const who = PEOPLE[persona];
  const live = rows.filter((r) => r.status !== "rejected");
  const within = live.filter((r) => r.e.initial === "within_threshold" && state !== "g");
  const review = live.filter((r) => !within.includes(r));
  const done = new Set<ProposedEntryStatus>([
    "approved",
    "posted",
    "failed_post",
    "recorded_externally",
  ]);
  const posted = rows.every((r) => r.status === "posted");
  return {
    items: rows.map((r) => ({
      entry_id: entryId(r.e.ref),
      ref: r.e.ref,
      description: r.e.title,
      amount: r.e.amount,
      status: r.status,
      class_limit:
        r.e.account_class === null || r.e.class_limit === null || state === "g"
          ? null
          : { account_class: r.e.account_class, limit: r.e.class_limit },
      approval_label: r.label,
      reverses_on: r.e.reverses_on,
      external_txn_ref: r.status === "posted" ? r.e.qbo_id : null,
      version: 1,
      allowed_actions: allowed(r, persona),
      // C-02-T31: CLS-07e's Retry and its red line (the reason by code, never provider text).
      posting_batch_id: r.status === "posted" || r.status === "failed_post" ? BATCH_ID : null,
      failure_line:
        r.status === "failed_post"
          ? "QuickBooks Online: account 'Accumulated Depreciation' is inactive"
          : null,
    })),
    total: rows.length,
    tallies: {
      proposed: tally(live),
      within_threshold: tally(within),
      review_required: tally(review),
      approved: live.filter((r) => done.has(r.status)).length,
      of: live.length,
      posted_batch_code: posted ? POSTED_BATCH : null,
      // C-02-T31: CLS-07d's banner (Sep 14, 10:22 AM CDT).
      posted_batch_id: posted ? BATCH_ID : null,
      posted_count: posted ? rows.length : null,
      posted_amount: posted ? tally(live).amount : null,
      posted_at: posted ? "2026-09-14T10:22:00-05:00" : null,
      closing_date_set: posted ? "2026-08-31" : null,
      resolved_failure_count: 0,
    },
    approver: {
      user_id: stableId(`user:${persona}`),
      display_name: who.name,
      role_label: who.role,
      policy_label: POLICY,
      policy_version_id: stableId("aje-policy:bh-aje-thresholds-v2"),
      may_batch_within_threshold: true,
    },
    posting_enabled: state !== "g",
    is_attest_client: state === "g",
  };
}

/** The detail pane's lines (C8 `GET …/proposed-entries`): only where the handoff names them. */
export function entries(state: Cls07Fixture): EntryOut[] {
  return rowsOf(state).map((r) => ({
    id: entryId(r.e.ref),
    ref: r.e.ref,
    kind: "aje",
    description: r.e.title,
    amount: r.e.amount,
    status: (["proposed", "within_threshold", "review_required", "approved"] as const).includes(
      r.status as "approved",
    )
      ? (r.status as EntryOut["status"])
      : "approved",
    threshold_result: r.e.initial === "within_threshold" ? "within_threshold" : "review_required",
    approval_label: r.label,
    is_attest_client: state === "g",
    allowed_actions: [],
    version: 1,
    lines: r.e.lines.map((l, i) => ({
      line_no: i + 1,
      account_code: l.account,
      account_name: l.account,
      debit: l.debit,
      credit: l.credit,
      fs_line_key: null,
    })),
  }));
}

/** The count of lines a row shows (the handoff's Lines column, even where lines are not named). */
export function lineCount(ref: string): number {
  return ENTRIES.find((e) => e.ref === ref)?.line_count ?? 0;
}

/** C-02-T31: CLS-07 c2's dry run: "Post 6 entries ($35,300.00) to QuickBooks Online · Copperleaf
 * Coffee Roasters? The closing date will be set to Aug 31, 2026." Nothing is written. */
export function dryRun(state: Cls07Fixture) {
  const approved = rowsOf(state).filter((r) => r.status === "approved");
  return {
    entry_count: approved.length,
    total_amount: tally(approved).amount,
    ledger_label: "QuickBooks Online",
    client_entity_name: "Copperleaf Coffee Roasters",
    closing_date_target: "2026-08-31",
    results: approved.map((r) => ({ entry_id: entryId(r.e.ref), ok: true })),
  };
}

/** The batch drawer's read after a post or a Retry (C8 v2 `PostingBatchOut`). */
export function batchView(state: Cls07Fixture) {
  const rows = rowsOf(state).filter((r) => r.status !== "rejected");
  return {
    batch_id: BATCH_ID,
    batch_code: POSTED_BATCH,
    period: "2026-08",
    status: "posting",
    entry_count: rows.length,
    total_amount: tally(rows).amount,
    closing_date_target: "2026-08-31",
    failure_count: state === "e" ? 1 : 0,
    resolved_failure_count: 0,
    undo_until: null,
    entries: [],
    version: 2,
  };
}
