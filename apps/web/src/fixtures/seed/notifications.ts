// Hannah Leclerc's notifications (SHL-04; P-01-T07): rows a–i at Mon Sep 14, 9:41 AM CT, the R2
// rows of frame g at Thu Oct 1, 11:00 AM CT, the Raj Malhotra Approvals variant, and the
// Notification settings kinds. Titles, contexts and times are verbatim from the SHL-04 spec, its
// R2 revision and the canvas's built frames (which give the trigger rows' times). The rows tie to
// TPL-02: TB complete 9:26, Keystone 8:47 already Received ✓, Harborline 8:52 Uploaded – needs
// review, $16,812,400.00, the Oct 9 report target and the Oct 15 Form 5500.
//
// Typed with the generated C16 types (docs/contracts/notifications.md; P-01-T01). Kind codes,
// categories and actor kinds follow the contract and the P-01 epic; the catalogue itself
// (P-01-T06) owns them. Row d's facts are the contract's §8 example. Every row's `facts` also carry
// its verbatim `title` and `context` until the kind templates exist. A row's order is the
// artboard's, not the clock's.

import type {
  NotificationFeedOut,
  NotificationItemOut,
  NotificationPreferenceOut,
} from "@abacus/api-client";
import type { InlineAction, NotificationCategory, NotificationTab } from "../contracts/shell";
import { type Seed } from "./index";
import { stableId } from "./prng";
import { SEATS, slugOf } from "./people";

/** The SHL-04 a–f clock (spec; the README's "Thu Oct 1" is a review fixture). */
export const SHL04_INSTANT = "2026-09-14T09:41:00-05:00";
/** The SHL-04 g and settings-menu clock (R2 frame 7). */
export const SHL04_R2_INSTANT = "2026-10-01T11:00:00-05:00";

export type RowKey = "a" | "b" | "c" | "d" | "e" | "f" | "g" | "h" | "i";
export type R2RowKey = "t1" | "t2" | "t3" | "t4";

export interface SeedNotification {
  /** The artboard row ("a"…"i", "t1"…"t4", "raj"). */
  row: string;
  kind: string;
  category: NotificationCategory;
  actorKind: NotificationItemOut["actor"]["kind"];
  /** The acting seat holder's initials, when a person acted. */
  actor: string | null;
  /** Lucide glyph in the 22 px chip. */
  glyph: string;
  /** The day-group label the row sits under. */
  day: string;
  title: string;
  context: string;
  /** The artboard's time label; the footing test ties `createdAt` to it. */
  timeLabel: string;
  createdAt: string;
  read: boolean;
  /** Waiting on the viewer: listed under Approvals. */
  pending: boolean;
  inlineActions: InlineAction[];
  /** A deep-link button on the row (never an action). */
  button?: string;
  /** Micro pill (row a). */
  pill?: string;
  /** Which engagement the row belongs to, by seed label. */
  engagement: "A1" | "A2" | null;
  /** The subject's object type when it is not the kind's own record. */
  subjectType?: string;
}

const TODAY = "Today";
const FRIDAY = "Friday, September 11";
const MONDAY_28 = "Monday, September 28";

/** Rows a–i, in the artboard's order. 4 unread (a–d). */
export const ROWS: readonly SeedNotification[] = [
  {
    row: "a",
    kind: "decision_assigned",
    category: "approval",
    actorKind: "system",
    actor: null,
    glyph: "CircleHelp",
    day: TODAY,
    title: "Materiality is blocked on a partner decision",
    context: "Northwind Robotics 401(k) Plan · waiting on Margaret Okonkwo since 9:27 AM",
    timeLabel: "9:27 AM",
    createdAt: "2026-09-14T09:27:00-05:00",
    read: false,
    pending: true,
    inlineActions: [],
    pill: "Blocked on a partner decision",
    engagement: "A1",
  },
  {
    row: "b",
    kind: "sign_off_requested",
    category: "approval",
    actorKind: "human",
    actor: "MD",
    glyph: "CircleCheck",
    day: TODAY,
    title: "Marcus Delaney signed off Trial Balance (L1)",
    context: "Northwind · Version 1 · ready for your review (L2)",
    timeLabel: "9:33 AM",
    createdAt: "2026-09-14T09:33:00-05:00",
    read: false,
    pending: true,
    inlineActions: ["open_sign_off"],
    button: "Sign off…",
    engagement: "A1",
  },
  {
    row: "c",
    kind: "run_finished",
    category: "run",
    actorKind: "agent",
    actor: null,
    glyph: "RefreshCw",
    day: TODAY,
    title: "Trial Balance workpaper complete",
    context: "Northwind · Agent run #4127 · agreed to Harborline net trust assets $16,812,400.00",
    timeLabel: "9:26 AM",
    createdAt: "2026-09-14T09:26:00-05:00",
    read: false,
    pending: false,
    inlineActions: [],
    engagement: "A1",
  },
  {
    row: "d",
    kind: "client_uploaded",
    category: "client_activity",
    actorKind: "human",
    actor: null,
    glyph: "Upload",
    day: TODAY,
    title: "Harborline Trust Company uploaded the certified trust report",
    context:
      "Northwind · matched to request ‘Certified trust report (full year, signed)’ · 96% match · Uploaded – needs review",
    timeLabel: "8:52 AM",
    createdAt: "2026-09-14T08:52:00-05:00",
    read: false,
    pending: true,
    inlineActions: ["accept_document", "return_document"],
    engagement: "A1",
    subjectType: "evidence_version",
  },
  {
    row: "e",
    kind: "mention",
    category: "mention",
    actorKind: "human",
    actor: "MO",
    glyph: "AtSign",
    day: TODAY,
    title: "Margaret Okonkwo mentioned you",
    context:
      "‘@Hannah did the bridge letter request go to Keystone for Oct–Dec 2025?’ · AUD-03 Source Documents",
    timeLabel: "8:31 AM",
    createdAt: "2026-09-14T08:31:00-05:00",
    read: true,
    pending: false,
    inlineActions: [],
    engagement: "A1",
  },
  {
    row: "f",
    kind: "run_finished",
    category: "run",
    actorKind: "agent",
    actor: "HL",
    glyph: "RefreshCw",
    day: TODAY,
    title: "Season Progress Reporter finished",
    context: "Workbench · Hannah Leclerc via Agent · 1 artifact · 2 m 41 s",
    timeLabel: "9:02 AM",
    createdAt: "2026-09-14T09:02:00-05:00",
    read: true,
    pending: false,
    inlineActions: [],
    engagement: null,
  },
  {
    row: "g",
    kind: "client_uploaded",
    category: "client_activity",
    actorKind: "human",
    actor: null,
    glyph: "Upload",
    day: TODAY,
    title: "Sam Ortiz (Keystone Retirement Services) uploaded Schedule of Account Balances",
    context: "Northwind · accepted by Marcus Delaney 8:55 AM · Received ✓",
    timeLabel: "8:47 AM",
    createdAt: "2026-09-14T08:47:00-05:00",
    read: true,
    pending: false,
    inlineActions: [],
    engagement: "A1",
    subjectType: "evidence_version",
  },
  {
    row: "h",
    kind: "run_needs_input",
    category: "run",
    actorKind: "agent",
    actor: null,
    glyph: "CircleHelp",
    day: FRIDAY,
    title: "Accrued Agent needs your answer",
    context:
      "Workbench · Granite Peak preliminary analytics — ‘Use FY2025 audited or FY2026 unaudited balances as the expectation base?’",
    timeLabel: "2:05 PM",
    createdAt: "2026-09-11T14:05:00-05:00",
    read: true,
    pending: false,
    inlineActions: [],
    engagement: null,
  },
  {
    row: "i",
    kind: "deadline_approaching",
    category: "deadline",
    actorKind: "system",
    actor: null,
    glyph: "Timer",
    day: FRIDAY,
    title: "Report target in 28 days",
    context: "Northwind PY2025 · report Oct 9 · Form 5500 (5558 extension) due Oct 15",
    timeLabel: "9:00 AM",
    createdAt: "2026-09-11T09:00:00-05:00",
    read: true,
    pending: false,
    inlineActions: [],
    engagement: "A1",
  },
];

/** Frame g (R2): one row of each new kind. 2 unread. */
export const R2_ROWS: readonly SeedNotification[] = [
  {
    row: "t1",
    kind: "todo_assigned",
    category: "other",
    actorKind: "human",
    actor: "MO",
    glyph: "CircleCheck",
    day: TODAY,
    title: "Margaret Okonkwo assigned you a to-do",
    context: "‘Update skill BH-SK-410’ · from Insights › Efficiency · due Oct 16",
    timeLabel: "9:58 AM",
    createdAt: "2026-10-01T09:58:00-05:00",
    read: false,
    pending: false,
    inlineActions: [],
    button: "Open to-do",
    engagement: null,
  },
  {
    row: "t2",
    kind: "template_update_available",
    category: "system",
    actorKind: "agent",
    actor: null,
    glyph: "Layers",
    day: TODAY,
    title: "Template update available: BH Audit Methodology · FS v6",
    context:
      "Granite Peak FY2026 is pinned to FS v5 · planning approved Sep 14 · rollout action Hold",
    timeLabel: "9:00 AM",
    createdAt: "2026-10-01T09:00:00-05:00",
    read: false,
    pending: false,
    inlineActions: [],
    button: "Review update…",
    engagement: "A2",
  },
  {
    row: "t3",
    kind: "trigger_run_finished",
    category: "run",
    actorKind: "agent",
    actor: null,
    glyph: "Zap",
    day: MONDAY_28,
    title: "Evidence screening finished",
    context:
      "Auto-started by trigger · Request status changes to Received · Granite Peak FY2026 · 2 corrected SURL files · both passed",
    timeLabel: "3:12 PM",
    createdAt: "2026-09-28T15:12:00-05:00",
    read: true,
    pending: false,
    inlineActions: [],
    engagement: "A2",
  },
  {
    row: "t4",
    kind: "trigger_run_finished",
    category: "run",
    actorKind: "agent",
    actor: null,
    glyph: "Zap",
    day: MONDAY_28,
    title: "Unrecorded liabilities tester finished",
    context:
      "Auto-started by trigger · Request evidence uploaded · Granite Peak FY2026 · BH-FS-430",
    timeLabel: "11:46 AM",
    createdAt: "2026-09-28T11:46:00-05:00",
    read: true,
    pending: false,
    inlineActions: [],
    engagement: "A2",
  },
];

/**
 * The Approvals row a viewer with close rights also sees (SHL-04 spec state 2, "e.g., Raj
 * Malhotra"); deep-link only. Its time is the run that proposed the entries, Sep 2, 2:14 PM
 * (the SHL-10e close activity on the same canvas).
 */
export const RAJ_ROW: SeedNotification = {
  row: "raj",
  kind: "proposal_routed",
  category: "approval",
  actorKind: "agent",
  actor: null,
  glyph: "CircleCheck",
  day: "Wednesday, September 2",
  title: "Accrued Agent proposed 4 entries within BH AJE thresholds v2 — Copperleaf August close",
  context: "",
  timeLabel: "2:14 PM",
  createdAt: "2026-09-02T14:14:00-05:00",
  read: false,
  pending: true,
  inlineActions: [],
  engagement: null,
};

/** SHL-04c: the receipt that replaces row d after Accept, with Undo for 10 s. */
export const ACCEPT_RECEIPT = "✓ Accepted by Hannah Leclerc · 9:42 AM";
export const ACCEPTED_AT = "2026-09-14T09:42:00-05:00";
export const UNDO_SECONDS = 10;
/** The request row d is matched to (Northwind PBC list; uploaded → received on Accept). */
export const ROW_D_REQUEST = "Certified trust report (full year, signed)";
/** Row d's facts, as the C16 contract's §8 example names them. */
export const ROW_D_FACTS: NotificationItemOut["facts"] = {
  client_display_name: "Harborline Trust Company",
  document_name: "certified trust report",
  match_percent: 96,
  item_status: "Uploaded – needs review",
  seen_proposal: stableId("seen-proposal:northwind:certified-trust-report"),
};

export const EMPTY_ALL = {
  title: "You're all caught up.",
  body: "Approvals, mentions, client uploads and finished runs appear here.",
};
export const EMPTY_APPROVALS = {
  title: "No approvals waiting on you.",
  body: "Decisions, sign-offs and agent proposals that need you appear here.",
};
export const SHOWING_DAYS = "Showing 30 days";
export const OPEN_APPROVALS_QUEUE = "Open approvals queue →";

/** The Notification settings menu (R2): the four kinds, "In Accrued · Email". The built canvas
 * has Mention and To-do assigned email on; the other two in-app only. */
export const PREFERENCE_KINDS: readonly (NotificationPreferenceOut & {
  label: string;
  glyph: string;
})[] = [
  { kind: "mention", label: "Mention", glyph: "AtSign", in_app: true, email: true },
  {
    kind: "todo_assigned",
    label: "To-do assigned",
    glyph: "CircleCheck",
    in_app: true,
    email: true,
  },
  {
    kind: "template_update_available",
    label: "Template update available",
    glyph: "Layers",
    in_app: true,
    email: false,
  },
  {
    kind: "trigger_run_finished",
    label: "Trigger run finished",
    glyph: "Zap",
    in_app: true,
    email: false,
  },
];

export function preferences(): NotificationPreferenceOut[] {
  return PREFERENCE_KINDS.map(({ kind, in_app, email }) => ({ kind, in_app, email }));
}

const userIdOf = (initials: string): string | null => {
  const seat = SEATS.find((s) => s.initials === initials);
  return seat === undefined ? null : stableId(`user:${slugOf(seat.name)}`);
};

/** The id of the Northwind request a row's facts point at. */
export function requestIdOf(seed: Seed, title: string): string | undefined {
  const a1 = seed.engagementIds.A1;
  return a1 === undefined
    ? undefined
    : seed.requestItems[a1]?.find((r) => r.description === title)?.id;
}

/** One seed row on the wire. `accepted` turns row d into its SHL-04c receipt. */
export function toWire(
  seed: Seed,
  row: SeedNotification,
  options: { read?: boolean; accepted?: boolean } = {},
): NotificationItemOut {
  const accepted = options.accepted === true && row.row === "d";
  const facts: NotificationItemOut["facts"] = { title: row.title, context: row.context };
  if (row.pill !== undefined) facts.pill = row.pill;
  if (row.button !== undefined) facts.button = row.button;
  if (row.row === "d") {
    Object.assign(facts, ROW_D_FACTS);
    facts.request_item_id = requestIdOf(seed, ROW_D_REQUEST) ?? null;
  }
  if (accepted) facts.receipt = ACCEPT_RECEIPT;
  return {
    id: stableId(`notification:hannah-leclerc:${row.row}`),
    kind: row.kind,
    category: row.category,
    created_at: row.createdAt,
    read: accepted || (options.read ?? row.read),
    actor: { kind: row.actorKind, user_id: row.actor === null ? null : userIdOf(row.actor) },
    subject: {
      type: row.subjectType ?? row.kind,
      id: stableId(`notification-subject:${row.row}`),
    },
    engagement_id: row.engagement === null ? null : (seed.engagementIds[row.engagement] ?? null),
    facts,
    inline_actions: accepted ? [] : [...row.inlineActions],
    pending: accepted ? false : row.pending,
  };
}

function inTab(n: NotificationItemOut, tab: NotificationTab): boolean {
  if (tab === "approvals") return n.pending;
  if (tab === "mentions") return n.category === "mention";
  if (tab === "client_activity") return n.category === "client_activity";
  return true;
}

/**
 * A `GET /v1/notifications/feed` page for one tab. Counts are the artboard's: Approvals counts
 * rows still pending, Mentions counts mentions, and the Client activity tab shows no count (the
 * contract's §8 example has it 0).
 */
export function pageOf(
  items: readonly NotificationItemOut[],
  tab: NotificationTab,
): NotificationFeedOut {
  return {
    items: items.filter((n) => inTab(n, tab)),
    next_cursor: null,
    counts: {
      approvals: items.filter((n) => n.pending).length,
      mentions: items.filter((n) => n.category === "mention").length,
      client_activity: 0,
    },
    unread_count: items.filter((n) => !n.read).length,
  };
}
