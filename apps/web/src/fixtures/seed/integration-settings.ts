// ADM-08 · Integration settings on fixtures (T-01-T40; docs/screens/ADM-08.md; handoff spec
// "ADM-08"): the CCH Axcess Tax file bridge (`EngineSettingsOut` as T-01-T20's route answers it),
// and the Ledgers and Mailboxes segments on the same shape (fixture mode only until their epics'
// routes exist). Synthetic Brightwater Hale seed, the handoff's values verbatim; Felix Andersen
// on Mon Sep 14, 2026 at 9:24 AM CT.
import type { EngineSettingsOut, FormatCheckOut, MappingRowOut } from "@abacus/api-client";
import { teamOf } from "./firm-people";
import { SEATS } from "./people";

export const ENGINE_KEY = "cch_axcess";
export const LEDGERS_KEY = "ledgers";
export const MAILBOXES_KEY = "mailboxes";

const cell = (key: string, value: string, lockReason: string | null = null) => ({
  key,
  value,
  locked: lockReason !== null,
  lock_reason: lockReason,
});

/** The tax team (firm-people's Tax team) and the CCH staff ID each is mapped to. The handoff
 * gives no IDs, so the fixture's convention is `BH-<initials>` (DEC-1568). */
export const TAX_TEAM: readonly [string, string][] = SEATS.filter((s) => teamOf(s) === "Tax").map(
  (s) => [s.name, `BH-${s.initials}`],
);

/** The workflow status mirror (01 §3.3.1 status words on the Accrued side). */
export const STATUS_MIRROR: readonly [string, string, "one_way" | "two_way"][] = [
  ["Not started", "Not Started", "one_way"],
  ["Gathering", "Waiting on Client", "one_way"],
  ["Preparing", "In Preparation", "one_way"],
  ["Prepared", "Ready for Review", "one_way"],
  ["In review", "In Review", "one_way"],
  ["Action required", "On Hold – Issues", "one_way"],
  ["Approved", "Review Complete", "one_way"],
  ["Ready for export", "Ready to Process", "one_way"],
  ["Awaiting signature", "Awaiting 8879", "one_way"],
  ["Filed", "E-filed", "one_way"],
  ["Accepted", "Complete", "one_way"],
  ["Due date", "Due date", "two_way"],
  ["Preparer / reviewer", "Assigned staff", "two_way"],
];

const row = (
  kind: MappingRowOut["kind"],
  source: string,
  target: string,
  direction: MappingRowOut["direction"] = null,
): MappingRowOut => ({ kind, source_key: source, target_value: target, direction });

/** f: "In Review" mapped twice (Prepared also maps to it): 409 `mapping_conflict` on Save. */
function mirror(state: string): MappingRowOut[] {
  return STATUS_MIRROR.map(([from, to, direction]) =>
    row(
      "workflow_status",
      from,
      state === "f" && from === "Prepared" ? "In Review" : to,
      direction,
    ),
  );
}

export function engineSettings(state: string): EngineSettingsOut {
  return {
    key: ENGINE_KEY,
    mode: "file_bridge",
    enabled: true,
    version: 3,
    allowed_actions: ["integration.configure", "integration.test"],
    cells: [
      cell("connection", "Firm token · connected by Felix Andersen Jan 16, 2026"),
      cell("last_sync", "Today 9:22 AM"),
      cell("return_id_template", "{Tax year}{Type}:{Client code}:V{n}"),
      cell(
        "client_code_rule",
        "Individuals: last name + first initial · Entities: first word of the name only",
      ),
      cell("new_version_on_import", "on"),
      cell("export_after_final_approval", "on", "BH-TAX-02: the signing partner approves first."),
      cell("who_may_export", "Tax Reviewer, Manager, Partner"),
      cell("import_requires_approval", "on"),
      cell("read_diagnostics", "on"),
      cell("efile_status_every", "Every 30 minutes"),
      cell("status_mirror", "on"),
    ],
    mappings: [
      ...TAX_TEAM.map(([name, id]) => row("user", name, id)),
      row("office", "Chicago (CHI)", "CHI-01 · Chicago"),
      row("office", "Denver (DEN)", "DEN-01 · Denver"),
      row("office", "New York (NYC)", "NYC-01 · New York"),
      ...mirror(state),
    ],
  };
}

/** b and e: the ledger posting rules; Sage Intacct needs reauth in e. */
export function ledgerSettings(state: string): EngineSettingsOut {
  return {
    key: LEDGERS_KEY,
    mode: "api",
    enabled: true,
    version: 1,
    allowed_actions: ["integration.configure", "integration.test"],
    cells: [
      cell("post_only_approved", "on", "Only human-approved batches post."),
      cell(
        "attest_clients",
        "Posting disabled — clients book proposed entries themselves",
        "Firm policy keeps Brightwater Hale out of audit and review clients' books (AICPA ET 1.295 nonattest services): those clients record proposed entries themselves.",
      ),
      cell("journal_memo", "BH AJE {period} · approved by {initials}"),
      cell("journal_prefix", "BH-"),
      cell("post_as", "Brightwater Hale (service user)"),
      cell("sage_intacct_state", state === "e" ? "needs_reauth" : "connected"),
    ],
    mappings: [
      row(
        "export_rules",
        "QuickBooks Online",
        "Copperleaf Coffee Roasters, Inc. (2026 Close · posting on · approver of record Ben Ashby)",
      ),
      row(
        "export_rules",
        "QuickBooks Online",
        "Ridgeline Property Partners, LP (tax · read-only)",
      ),
      row("export_rules", "NetSuite", "Granite Peak Outdoor Supply, Inc. (attest · posting off)"),
      row("export_rules", "NetSuite", "Ashford Manufacturing Co. (tax provision · read-only)"),
      row(
        "export_rules",
        "Sage Intacct",
        "Bluestem Analytics, LLC (2026 Close from Oct · posting on)",
      ),
      row("export_rules", "Xero", "Lakeshore Literacy Alliance (attest · posting off)"),
      row("export_rules", "Xero", "Juniper & Oak Interiors, LLC (2026 Close · posting on)"),
    ],
  };
}

export function mailboxSettings(): EngineSettingsOut {
  return {
    key: MAILBOXES_KEY,
    mode: "api",
    enabled: true,
    version: 1,
    allowed_actions: ["integration.configure"],
    cells: [
      cell("mailbox", "docs@brightwaterhale.com — Microsoft 365 · connected"),
      cell("auto_classify", "on"),
      cell("match_sender", "on"),
      cell("unmatched_senders", "4"),
      cell("route_upload_something_else", "on"),
      cell("notices_intake", "on"),
    ],
    mappings: [],
  };
}

/** d: the CCH file bridge reads three returns; e: Sage Intacct refuses (HTTP 403). */
export function testResult(key: string, state: string): FormatCheckOut {
  if (key === LEDGERS_KEY && state === "e") {
    return { ok: false, problems: ["HTTP 403 · permission denied"], returns_read: null };
  }
  return { ok: true, problems: [], returns_read: 3 };
}
