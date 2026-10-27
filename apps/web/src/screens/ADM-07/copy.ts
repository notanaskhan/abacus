// ADM-07 copy, verbatim from the handoff (screens/ADM-07 spec.md, ROWS 1–14, DETAIL DRAWER,
// STATES a–g) and docs/screens/ADM-07.md with the T03 deviations. The server sends action codes
// and facts (P-34); the titles and detail lines are composed here, so no wording is invented on
// the server and none of it ever names the agent as an actor ("‹person› via Agent", never
// "Accrued Agent").
import type { AuditActorOut, AuditEventRow } from "@abacus/api-client";

type Facts = NonNullable<AuditEventRow["detail_facts"]>;
type Labels = NonNullable<AuditEventRow["labels"]>;

export const COPY = {
  title: "Firm settings",
  navTitle: "Settings",
  back: "Back",
  section: "Audit log",
  count: (total: string) => `${total} events · immutable`,
  countOf: (shown: string, total: string) => `${shown} of ${total}`,
  immutable: "Immutable",
  policyNote: (n: number) =>
    n === 0
      ? "Policy principal: 0 events — policy acceptance is off (AI policy v3)."
      : `Policy principal: ${String(n)} events`,
  search: "Search activity",
  clearSearch: "Clear search",
  exportButton: "Export…",
  showing: (shown: string, total: string) => `Showing ${shown} of ${total}`,
  loadMore: "Load more",
  noMatch: (q: string) => `No events match '${q}'.`,
  noMatchBody: "Search covers actors, objects and details.",
  empty: "No events in this range.",
  error: "The audit log couldn't load.",
  retry: "Retry",
  notAllowed: "You don't have access to the audit log.",
  filters: {
    actor: "Actor",
    object: "Object",
    action: "Action",
    date: "Date",
    office: "Office",
    all: "All",
  },
  actorOptions: [
    { value: "person", label: "People" },
    { value: "via_agent", label: "via Agent" },
    { value: "policy", label: "Policy principal" },
    { value: "system", label: "System" },
  ],
  dateOptions: [
    { value: "7d", label: "Past 7 days" },
    { value: "30d", label: "Past 30 days" },
    { value: "90d", label: "Past 90 days" },
  ],
  objectOptions: [
    { value: "engagement", label: "Engagements" },
    { value: "close", label: "Closes" },
    { value: "tax_return", label: "Tax returns" },
    { value: "client", label: "Clients" },
    { value: "wall", label: "Walls" },
    { value: "agent_run", label: "Agent runs" },
    { value: "auth_session", label: "Sign-ins" },
  ],
  actionOptions: [
    { value: "decision", label: "Decisions" },
    { value: "change", label: "Changes" },
    { value: "access", label: "Access" },
    { value: "run", label: "Runs" },
    { value: "sign_in", label: "Sign-ins" },
    { value: "communication", label: "Messages" },
    { value: "export", label: "Exports" },
  ],
  tags: {
    person: "Person",
    via_agent: "via Agent",
    policy: "Policy",
    system: "System",
    support: "Support",
  } satisfies Record<AuditActorOut["kind"], string>,
  marks: { ok: "Approved or signed off", no: "Reversed or removed", pl: "Event" },
  run: "Run ›",
  plannedRun: "Opens the run trace (WB-09), not built yet",
  filterByIp: (ip: string) => `Filter by IP ${ip}`,
  rowName: (title: string, object: string, when: string) => `${title}, ${object}, ${when}`,
  noIp: "—",
  today: "Today",
  // The drawer (c).
  drawer: {
    close: "Close",
    actor: "Actor",
    authority: "Authority",
    time: "Time",
    ipDevice: "IP / device",
    session: "Session",
    contentHash: "Content hash",
    beforeAfter: "Before → after",
    notIncluded: "Not included",
    source: "Source",
    openRun: "Open run trace ›",
    footer: "Immutable. Corrections are new events.",
    entry: "Entry",
    amount: "Amount",
    status: "Status before → after",
    total: "Total",
    withheld: "Values are visible to partners in scope.",
    notEnabled: "Values aren't shown for this firm yet.",
    unavailable: "Values unavailable",
  },
  // Export… (e) and its ready state (g).
  exportDialog: {
    title: "Export audit log",
    range: "Range",
    format: "Format",
    formatValue: "CSV + signed JSON manifest",
    includeValues: "Include before/after values",
    submit: "Export",
    cancel: "Cancel",
    ready: "Export ready · SHA-256 manifest included",
    failed: "The export couldn't start.",
  },
  stepUpTitle: "Confirm it's you to export the audit log",
  stepUpBody:
    "Exporting the audit log needs a recent sign-in. Sign in again, then export once more. If it still isn't allowed, your role doesn't permit it.",
  signInAgain: "Sign in again",
} as const;

/** Who acted, in the actor grammar: "Raj Malhotra", "Hannah Leclerc via Agent", "Policy: BH AJE
 * thresholds v2", "System". */
export function actorName(actor: AuditActorOut, labels: Labels = {}): string {
  switch (actor.kind) {
    case "person":
      return actor.person?.display_name ?? "";
    case "via_agent":
      return `${actor.on_behalf_of?.display_name ?? ""} via Agent`;
    case "policy":
      return `Policy: ${labelOf(actor.policy_ref ?? "", labels)}`;
    case "support":
      return actor.person?.display_name ?? "Support";
    default:
      return "System";
  }
}

function labelOf(id: string, labels: Labels): string {
  return labels[id] ?? id;
}

const str = (facts: Facts, key: string): string | undefined => {
  const v = facts[key];
  return typeof v === "string" ? v : undefined;
};
const num = (facts: Facts, key: string): number | undefined => {
  const v = facts[key];
  return typeof v === "number" ? v : undefined;
};
const plural = (n: number, one: string, many: string): string =>
  `${String(n)} ${n === 1 ? one : many}`;

function duration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${String(m)} m ${String(s)} s` : `${String(s)} s`;
}

const SCHEDULES: Record<string, string> = {
  weekly_monday_0900_ct: "scheduled Mondays 9:00 AM CT",
  daily: "daily",
};
const REASONS: Record<string, string> = {
  irs_wage_income_transcript_match: "match to IRS wage & income transcript",
  asset_additions_unconfirmed: "Returned to review: asset additions not yet confirmed",
};
const DESTINATIONS: Record<string, string> = { cch_axcess_tax: "CCH Axcess Tax" };
const METHODS: Record<string, string> = {
  sso: "SSO",
  email_code: "Email code",
  passkey: "Passkey",
  totp: "Authenticator",
};

/** The 13.5/500 title: "{Verb} by {Actor}" (cch-sync), from the action code. */
export function titleOf(row: AuditEventRow): string {
  const facts = row.detail_facts ?? {};
  const labels = row.labels ?? {};
  const who = actorName(row.actor, labels);
  switch (row.action) {
    case "engagement_run.started":
      return `Engagement run started by ${who}`;
    case "workbench_session.started":
      return `Session started by ${who}`;
    case "wall.created":
      return `Ethical wall added by ${who}`;
    case "entry_batch.approved": {
      const policy = str(facts, "policy_ref");
      return policy === undefined
        ? `Entries approved by ${who}`
        : `Entries approved by ${who} under ${labelOf(policy, labels)}`;
    }
    case "entry_batch.accepted":
      return `Entries accepted by ${who}`;
    case "proposed_entry.acceptance_reversed":
      return `Acceptance reversed by ${who}`;
    case "inbox_email.received": {
      const from = str(facts, "from_contact_id");
      return `Email received from ${from === undefined ? who : labelOf(from, labels)}`;
    }
    case "agent_run.report_prepared":
      return `Report prepared by ${who}`;
    case "agent_run.reminders_drafted":
      return `Reminders drafted by ${who}`;
    case "envelope.sent":
      return `Envelope sent by ${who}`;
    case "pii.revealed":
      return `${(str(facts, "field") ?? "").toUpperCase() || "Number"} revealed by ${who}`;
    case "session.started":
      return `Signed in by ${who}`;
    case "acceptance_prescreen.drafted":
      return `Acceptance pre-screen drafted by ${who}`;
    case "tax_return.exported": {
      const to = DESTINATIONS[str(facts, "destination") ?? ""];
      return to === undefined ? `Return exported by ${who}` : `Return exported to ${to} by ${who}`;
    }
    case "tax_return.approved":
      return `Return approved by ${who}`;
    case "tax_return.self_checked":
      return `Initial draft self-checked by ${who}`;
    // The security center's own events (G-02-T14; ADM-06 "every change → ADM-07").
    case "security_policy.sso_enforced":
      return `SSO enforced by ${who}`;
    case "security_policy.updated":
      return `Sign-in policy changed by ${who}`;
    case "portal_security_policy.updated":
      return `Portal sign-in changed by ${who}`;
    case "sso_exempt_account.designated":
      return `Break-glass account designated by ${who}`;
    case "sso_exempt_account.cleared":
      return `Break-glass account cleared by ${who}`;
    case "session.signed_out":
      return `Session signed out by ${who}`;
    case "staff.unlocked":
      return `Sign-in unlocked by ${who}`;
    case "support_access.updated":
      return `Support access changed by ${who}`;
    case "firm_export.requested":
      return `Data export requested by ${who}`;
    default:
      return `${sentence(row.action)} by ${who}`;
  }
}

/** "wall.created" → "Wall created": the fallback for an action with no template. */
function sentence(action: string): string {
  const words = action.replace(/[._]/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** The 12.5 ink-2 detail line, from identifier-only facts and their labels. Values (amounts,
 * titles, numbers) are the drawer's, for readers in scope (DEC-60). */
export function detailOf(row: AuditEventRow, dateOf: (iso: string) => string): string {
  const facts = row.detail_facts ?? {};
  const labels = row.labels ?? {};
  const parts: string[] = [];
  switch (row.action) {
    case "engagement_run.started":
      if (str(facts, "plan_approval") === "yes_run_it")
        parts.push("Plan approved ('yes, run it')");
      if (facts.auto_mode === false) parts.push("Auto mode off");
      if (facts.auto_mode === true) parts.push("Auto mode on");
      break;
    case "wall.created": {
      const walled = str(facts, "walled_user_id");
      const client = str(facts, "client_id");
      const approver = str(facts, "approved_by_user_id");
      if (walled !== undefined && client !== undefined) {
        parts.push(`${labelOf(walled, labels)} ✕ ${labelOf(client, labels)}`);
      }
      if (approver !== undefined) parts.push(`approved by ${labelOf(approver, labels)}`);
      break;
    }
    case "entry_batch.approved":
    case "entry_batch.accepted": {
      const n = num(facts, "within_threshold");
      if (n !== undefined) parts.push(`${String(n)} within threshold`);
      if (facts.reversible === true) parts.push("reversible");
      break;
    }
    case "proposed_entry.acceptance_reversed": {
      const reason = REASONS[str(facts, "reason_code") ?? ""];
      if (reason !== undefined) parts.push(reason);
      break;
    }
    case "inbox_email.received": {
      const n = num(facts, "attachments");
      if (n !== undefined) parts.push(plural(n, "attachment", "attachments"));
      if (facts.filed === false) parts.push("waiting to be filed");
      break;
    }
    case "agent_run.report_prepared":
    case "agent_run.reminders_drafted": {
      const agent = str(facts, "agent_id");
      const schedule = SCHEDULES[str(facts, "schedule") ?? ""];
      const name = agent === undefined ? undefined : labelOf(agent, labels);
      if (row.action === "agent_run.reminders_drafted") {
        if (name !== undefined)
          parts.push(schedule === undefined ? name : `${name} (${schedule})`);
        const drafts = num(facts, "drafts");
        if (drafts !== undefined) parts.push(`${String(drafts)} drafts awaiting approval`);
        const sent = num(facts, "sent");
        if (sent !== undefined) parts.push(`${String(sent)} sent`);
      } else {
        if (name !== undefined) parts.push(name);
        if (schedule !== undefined) parts.push(schedule);
        const seconds = num(facts, "duration_s");
        if (seconds !== undefined) parts.push(duration(seconds));
        const artifacts = num(facts, "artifacts");
        if (artifacts !== undefined) parts.push(plural(artifacts, "artifact", "artifacts"));
      }
      break;
    }
    case "envelope.sent": {
      if (str(facts, "document_kind") === "engagement_letter") parts.push("Engagement letter");
      const signers = ["signer_1_id", "signer_2_id"]
        .map((k) => str(facts, k))
        .filter((v): v is string => v !== undefined)
        .map((v) => labelOf(v, labels));
      if (signers.length > 0) parts.push(`signers ${signers.join(", ")}`);
      break;
    }
    case "pii.revealed": {
      const reason = REASONS[str(facts, "reason_code") ?? ""];
      if (reason !== undefined) parts.push(`reason: ${reason}`);
      break;
    }
    case "session.started": {
      const method = METHODS[str(facts, "method") ?? ""];
      const provider = str(facts, "provider") === "microsoft" ? "Microsoft " : "";
      if (method !== undefined) parts.push(`${provider}${method}`);
      if (facts.mfa === true) parts.push("MFA");
      break;
    }
    case "acceptance_prescreen.drafted": {
      const flags = num(facts, "flags");
      if (flags !== undefined) parts.push(plural(flags, "flag", "flags"));
      if (str(facts, "awaiting") === "partner_decision") parts.push("awaiting partner decision");
      if (facts.return_information_read === false) {
        parts.push("no return information read (no §7216 consent yet)");
      }
      break;
    }
    case "tax_return.exported":
      if (facts.synced === true) parts.push(`Synced ${dateOf(row.effective_at)}`);
      break;
    case "tax_return.approved": {
      const gate = str(facts, "gate");
      if (gate !== undefined)
        parts.push(`Final approval (${gate.toUpperCase().replace(/_/g, "-")})`);
      const open = num(facts, "open_review_items");
      if (open !== undefined) parts.push(`${String(open)} open review items`);
      break;
    }
    case "tax_return.self_checked":
      if (facts.routing_check_only === true) parts.push("Routing check only — not an approval");
      break;
    default:
      break;
  }
  return parts.join(" · ");
}

/** The detail drawer's header: "Entries approved · Copperleaf · 2026-08". */
export function drawerTitle(row: AuditEventRow): string {
  const verb = titleOf(row).split(" by ")[0] ?? "";
  const label = row.target.label ?? "";
  return label === "" ? verb : `${verb} · ${label}`;
}

type AuthorityFacts = Readonly<Record<string, string | number | boolean | null>>;
const factText = (v: string | number | boolean | null | undefined): string =>
  v === null || v === undefined ? "" : String(v);

export const AUTHORITY: Record<string, (facts: AuthorityFacts) => string> = {
  within_threshold_batch: (facts) => {
    const limit = factText(facts.approval_limit);
    return `Within ${factText(facts.policy)} · approval limit: ${LEVEL_WORDS[limit] ?? limit}, within-threshold batch`;
  },
};

export const STATUS_WORDS: Record<string, string> = {
  within_threshold: "Within threshold",
  approved: "Approved",
};

export const NOT_INCLUDED: Record<string, string> = {
  review_required_other_accruals_over_10000: "Review required (> $10,000 other accruals)",
};

const LEVEL_WORDS: Record<string, string> = { senior: "Senior", manager: "Manager" };

export const LEVELS: Record<string, string> = {
  senior: "Senior",
  manager: "Manager",
  partner: "Partner",
  admin: "Admin",
};
