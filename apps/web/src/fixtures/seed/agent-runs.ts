// C6 v1.1's E0 runs (P-09-T01; TASK-6201; DEC-2801), verbatim from the WB-09 and SHL-13 handoffs:
// #4118 Season Progress Reporter (Sep 14, 9:00 AM CT), #4127 the Northwind PY2025 planning run
// (Sep 14, 9:24 AM CT, a 9:41 snapshot), the Aug 17 failed run (CCH Axcess Tax 401) and Copperleaf
// Run 2 (CLS-02's close run). Every figure foots in code: 224 + 214 + 241 + 1,946 = 2,625 records;
// 9:00:00 → 9:02:41 = 2 m 41 s; 10 + 26 + 26 + 17 = 79 open returns; 6 of 9 close steps done.
import type {
  AgentRunOut,
  RecordsReadOut,
  RunItemOut,
  RunTraceOut,
  RunViewOut,
  RunWriteOut,
  TraceRowOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export type E0Run = {
  view: RunViewOut;
  trace: RunTraceOut;
  items: RunItemOut[];
  recordsRead: RecordsReadOut[];
  writes: RunWriteOut[];
};

const RUNTIME = "Accrued Agent runtime";
const REGION = "United States (data and inference)";
const TRAINING = "Firm data is never used for training";
const SHA = `sha256:${"0".repeat(64)}`;
const CONTENT_ACTIONS = ["agent_run.read", "run_trace.export"];

/** 9:00 AM CT on Mon Sep 14, 2026 is 14:00 UTC (CDT). */
function sep14(hms: string): string {
  const [h, m, s] = hms.split(":").map(Number);
  return new Date(Date.UTC(2026, 8, 14, (h ?? 0) + 5, m ?? 0, s ?? 0)).toISOString();
}

function row(
  seq: number,
  at: string,
  fields: Omit<TraceRowOut, "seq" | "at" | "actor" | "detail"> &
    Partial<Pick<TraceRowOut, "actor" | "detail">>,
): TraceRowOut {
  return { seq, at, actor: null, detail: null, ...fields };
}

function sumRead(rows: RecordsReadOut[]): number {
  return rows.reduce((n, r) => n + r.count, 0);
}

// --- #4118: Season Progress Reporter, weekly run (WB-09 a) ---------------------------------------

export const RUN_4118_ID = stableId("agent-run:season-progress-reporter-4118");
const CCH = stableId("connection:cch-axcess-tax");

const RUN_4118: AgentRunOut = {
  id: RUN_4118_ID,
  agent: "season_progress_reporter",
  agent_label: "Season Progress Reporter v2",
  state: "succeeded",
  started_at: sep14("9:00:00"),
  finished_at: sep14("9:02:41"),
  duration_ms: 161_000,
  initiator_name: "Hannah Leclerc",
  subject: null,
};

const READ_4118: RecordsReadOut[] = [
  {
    source: "Tax returns",
    count: 224,
    connection_id: CCH,
    through: "CCH Axcess Tax (firm connection)",
  },
  { source: "Tax engagements", count: 214, connection_id: null, through: "Accrued" },
  { source: "Binders", count: 241, connection_id: null, through: "Accrued" },
  { source: "Activity events", count: 1946, connection_id: null, through: "Accrued" },
];

const WRITE_4118_ID = stableId("proposal:season-progress-4118-save-file");
const WRITES_4118: RunWriteOut[] = [
  {
    kind: "proposal",
    id: WRITE_4118_ID,
    target_type: "file",
    target_id: null,
    key: "save_file",
    outcome: "waiting",
    at: sep14("9:02:41"),
    decision: null,
    decided_by_name: null,
    decided_at: null,
    state: "waiting",
    approver_name: "Hannah Leclerc",
    proposal_id: WRITE_4118_ID,
  },
];

const ROWS_4118: TraceRowOut[] = [
  row(1, sep14("9:00:00"), {
    kind: "start",
    phase: "plan",
    mark: "start",
    title: "Run started",
    state: "done",
    detail:
      "Schedule Mondays at 9:00 AM CT · inputs Tax year 2025 · All offices · Open returns only",
  }),
  row(2, sep14("9:00:03"), {
    kind: "attempt",
    phase: "plan",
    mark: "plan",
    title: "Plan",
    state: "done",
    detail:
      "4 steps · 1 write needs approval · plan approved when the schedule was saved by Hannah Leclerc (Aug 10)",
  }),
  row(3, sep14("9:00:05"), {
    kind: "attempt",
    phase: "execute",
    mark: "done",
    title: "Execute › list returns",
    state: "done",
    detail: "tax year 2025 → 224 returns read (status from CCH Axcess Tax) · 1.9 s",
    duration_ms: 1_900,
  }),
  row(4, sep14("9:00:21"), {
    kind: "attempt",
    phase: "execute",
    mark: "done",
    title: "Execute › list engagements",
    state: "done",
    detail: "period 2025 → 214 read · 0.8 s",
    duration_ms: 800,
  }),
  row(5, sep14("9:00:34"), {
    kind: "attempt",
    phase: "execute",
    mark: "done",
    title: "Execute › read binders",
    state: "done",
    detail: "tax year 2025, request status → 241 read · 31.6 s",
    duration_ms: 31_600,
  }),
  row(6, sep14("9:01:10"), {
    kind: "attempt",
    phase: "execute",
    mark: "done",
    title: "Execute › read activity",
    state: "done",
    detail: "since Sep 7 → 1,946 events read · 22.4 s",
    duration_ms: 22_400,
  }),
  row(7, sep14("9:01:48"), {
    kind: "output",
    phase: "compute",
    mark: "done",
    title: "Compute › group by stage and office",
    state: "done",
    detail: "79 open returns: Gather 10 · Prepare 26 · Review 26 · Deliver 17",
  }),
  row(8, sep14("9:02:20"), {
    kind: "output",
    phase: "execute",
    mark: "done",
    title: "Execute › build workbook",
    state: "done",
    detail:
      "TY2025 Season Progress — week of Sep 14.xlsx · 5 tabs · 79 rows · each row cites its return",
  }),
  row(9, sep14("9:02:41"), {
    kind: "decision",
    phase: "proposed_write",
    mark: "waiting",
    title: "Proposed write › save file",
    state: "waiting",
    detail: "Files › Firm reports › TY2025 season · waiting on Hannah Leclerc",
  }),
];

const RUN_4118_E0: E0Run = {
  view: {
    run: RUN_4118,
    run_record_sha256: SHA,
    allowed_actions: CONTENT_ACTIONS,
    projection: "content",
    access: "content",
    header: {
      run_number: 4118,
      blocked_on: null,
      counters: {
        records_read: sumRead(READ_4118),
        citations_count: 79,
        writes_done: 0,
        writes_waiting: 1,
        agent_ms: 161_000,
        agent_minutes: 3,
      },
      runs_as_name: "Hannah Leclerc",
      trigger_kind: "schedule",
      work_item_ref: null,
    },
    levels: [
      { level: 1, total: 4, done: 4, running: 0, blocked: 0, waiting: 0, queued: 0, failed: 0 },
    ],
  },
  trace: {
    run: RUN_4118,
    runtime: RUNTIME,
    region: REGION,
    training: TRAINING,
    attempts: 6,
    tokens_in: 0,
    tokens_out: 0,
    rows: ROWS_4118,
    records_read: READ_4118,
    output_counts: [{ kind: "proposal", count: 1 }],
    model_text: null,
    projection: "content",
    access: "content",
    summary: {
      run_number: 4118,
      agent_label: "Season Progress Reporter v2",
      started_at: sep14("9:00:00"),
      trigger_kind: "schedule",
      runs_as_name: "Hannah Leclerc",
      duration_ms: 161_000,
      records_read: sumRead(READ_4118),
      citations: 79,
      writes_done: 0,
      writes_waiting: 1,
    },
  },
  items: [],
  recordsRead: READ_4118,
  writes: WRITES_4118,
};

// --- #4127: Northwind Robotics 401(k) Plan — PY2025 planning run (WB-09 b; SHL-13) ----------------

export const RUN_4127_ID = stableId("agent-run:northwind-py2025-planning-4127");

const RUN_4127: AgentRunOut = {
  id: RUN_4127_ID,
  agent: "audit_planning",
  agent_label: "Northwind Robotics 401(k) Plan — PY2025 planning run",
  state: "running",
  started_at: sep14("9:24:00"),
  finished_at: null,
  duration_ms: null,
  initiator_name: "Marcus Delaney",
  subject: null,
};

const ROWS_4127: TraceRowOut[] = [
  row(1, sep14("9:24:00"), {
    kind: "start",
    phase: "plan",
    mark: "plan",
    title: "Plan approved",
    state: "done",
    actor: "Marcus Delaney",
    detail: "yes, run it",
  }),
  row(2, sep14("9:26:00"), {
    kind: "attempt",
    phase: "execute",
    mark: "done",
    title: "Execute › Run trial balance workpaper",
    state: "done",
    detail: "Complete",
  }),
  row(3, sep14("9:27:00"), {
    kind: "decision",
    phase: "decision",
    mark: "blocked",
    title: "Propose materiality",
    state: "waiting",
    detail: "Blocked on a partner decision (Margaret Okonkwo)",
  }),
  row(4, sep14("9:31:00"), {
    kind: "attempt",
    phase: "execute",
    mark: "running",
    title: "Draft risk assessment",
    state: "running",
    detail: "Running",
  }),
  row(5, sep14("9:33:00"), {
    kind: "queued",
    phase: "execute",
    mark: "muted",
    title: "General audit planning",
    state: "waiting",
    detail: "Waiting on inputs: trust agreement, IRS opinion letter",
  }),
];

const RUN_4127_E0: E0Run = {
  view: {
    run: RUN_4127,
    run_record_sha256: SHA,
    allowed_actions: CONTENT_ACTIONS,
    projection: "content",
    access: "content",
    header: {
      run_number: 4127,
      blocked_on: {
        kind: "decision",
        id: null,
        role: "engagement_partner",
        user_id: null,
        needs: [],
      },
      counters: null,
      runs_as_name: "Marcus Delaney",
      trigger_kind: "manual",
      work_item_ref: null,
    },
    levels: [
      { level: 1, total: 4, done: 1, running: 1, blocked: 1, waiting: 1, queued: 0, failed: 0 },
    ],
  },
  trace: {
    run: RUN_4127,
    runtime: RUNTIME,
    region: REGION,
    training: TRAINING,
    attempts: 2,
    tokens_in: 0,
    tokens_out: 0,
    rows: ROWS_4127,
    records_read: [],
    output_counts: [],
    model_text: null,
    projection: "content",
    access: "content",
    summary: {
      run_number: 4127,
      agent_label: "Northwind Robotics 401(k) Plan — PY2025 planning run",
      started_at: sep14("9:24:00"),
      trigger_kind: "manual",
      runs_as_name: "Marcus Delaney",
      // "17 m so far" at the 9:41 snapshot.
      duration_ms: 17 * 60_000,
      records_read: 0,
      citations: 0,
      writes_done: 0,
      writes_waiting: 0,
    },
  },
  items: [],
  recordsRead: [],
  writes: [],
};

// --- The Aug 17 failed run (WB-09 c) --------------------------------------------------------------

export const RUN_AUG17_ID = stableId("agent-run:season-progress-reporter-aug-17");
const AUG17 = (s: number) => new Date(Date.UTC(2026, 7, 17, 14, 0, s)).toISOString();

const RUN_AUG17: AgentRunOut = {
  id: RUN_AUG17_ID,
  agent: "season_progress_reporter",
  agent_label: "Season Progress Reporter v2",
  state: "failed",
  state_reason: "connector_unauthorised",
  started_at: AUG17(0),
  finished_at: AUG17(14),
  duration_ms: 14_000,
  initiator_name: "Hannah Leclerc",
  subject: null,
};

const RUN_AUG17_E0: E0Run = {
  view: {
    run: RUN_AUG17,
    run_record_sha256: SHA,
    allowed_actions: CONTENT_ACTIONS,
    projection: "content",
    access: "content",
    header: {
      run_number: null,
      blocked_on: null,
      counters: null,
      runs_as_name: "Hannah Leclerc",
      trigger_kind: "schedule",
      work_item_ref: null,
    },
    levels: [
      { level: 1, total: 4, done: 0, running: 0, blocked: 0, waiting: 0, queued: 3, failed: 1 },
    ],
  },
  trace: {
    run: RUN_AUG17,
    runtime: RUNTIME,
    region: REGION,
    training: TRAINING,
    attempts: 1,
    tokens_in: 0,
    tokens_out: 0,
    rows: [
      row(1, AUG17(0), {
        kind: "start",
        phase: "plan",
        mark: "start",
        title: "Run started",
        state: "done",
      }),
      row(2, AUG17(14), {
        kind: "finish",
        phase: "execute",
        mark: "failed",
        title: "Execute › list returns",
        state: "failed",
        detail: "CCH Axcess Tax returned 401: token expired",
      }),
    ],
    records_read: [],
    output_counts: [],
    model_text: null,
    projection: "content",
    access: "content",
    summary: {
      run_number: null,
      agent_label: "Season Progress Reporter v2",
      started_at: AUG17(0),
      trigger_kind: "schedule",
      runs_as_name: "Hannah Leclerc",
      duration_ms: 14_000,
      records_read: 0,
      citations: 0,
      writes_done: 0,
      writes_waiting: 0,
    },
  },
  items: [],
  recordsRead: [],
  writes: [],
};

// --- Copperleaf Run 2: CLS-02's close run (SHL-13 frame 8, Raj Malhotra) -------------------------

export const RUN_COPPERLEAF_2_ID = stableId("agent-run:copperleaf-close-run-2");
export const COPPERLEAF_STEPS: { title: string; done: boolean }[] = [
  { title: "Import August GL from QuickBooks Online", done: true },
  { title: "Reconcile Front Range Bank ••4410", done: true },
  { title: "Reconcile Amex ••1009", done: true },
  { title: "Tie Square payouts (gross $73,166.90 − fees $1,684.54 = net $71,482.36)", done: true },
  { title: "Amortize prepaid insurance ($700)", done: true },
  { title: "Book depreciation ($2,140)", done: true },
  { title: "Accrue payroll", done: false },
  { title: "Recognize deferred subscription revenue", done: false },
  { title: "Flux review August vs July", done: false },
];
const COPPERLEAF_DONE = COPPERLEAF_STEPS.filter((s) => s.done).length;
const COPPERLEAF_RUNNING = COPPERLEAF_STEPS.length - COPPERLEAF_DONE;

const RUN_COPPERLEAF_2: AgentRunOut = {
  id: RUN_COPPERLEAF_2_ID,
  agent: "close_run",
  agent_label: "Closing agent",
  state: "running",
  // "Started 18 minutes ago" against SHL-13's 9:41 AM clock.
  started_at: sep14("9:23:00"),
  finished_at: null,
  duration_ms: null,
  initiator_name: "Raj Malhotra",
  subject: null,
};

const RUN_COPPERLEAF_2_E0: E0Run = {
  view: {
    run: RUN_COPPERLEAF_2,
    run_record_sha256: SHA,
    allowed_actions: CONTENT_ACTIONS,
    projection: "content",
    access: "content",
    header: {
      run_number: 2,
      blocked_on: null,
      counters: null,
      runs_as_name: "Raj Malhotra",
      trigger_kind: "manual",
      work_item_ref: null,
    },
    levels: [
      {
        level: 1,
        total: COPPERLEAF_STEPS.length,
        done: COPPERLEAF_DONE,
        running: COPPERLEAF_RUNNING,
        blocked: 0,
        waiting: 0,
        queued: 0,
        failed: 0,
      },
    ],
  },
  trace: {
    run: RUN_COPPERLEAF_2,
    runtime: RUNTIME,
    region: REGION,
    training: TRAINING,
    attempts: COPPERLEAF_DONE,
    tokens_in: 0,
    tokens_out: 0,
    rows: COPPERLEAF_STEPS.map((s, i) =>
      row(i + 1, sep14("9:23:00"), {
        kind: "attempt",
        phase: "execute",
        mark: s.done ? "done" : "running",
        title: s.title,
        state: s.done ? "done" : "running",
      }),
    ),
    records_read: [],
    output_counts: [],
    model_text: null,
    projection: "content",
    access: "content",
    summary: null,
  },
  items: [],
  recordsRead: [],
  writes: [],
};

export const E0_RUNS: Record<string, E0Run> = {
  [RUN_4118_ID]: RUN_4118_E0,
  [RUN_4127_ID]: RUN_4127_E0,
  [RUN_AUG17_ID]: RUN_AUG17_E0,
  [RUN_COPPERLEAF_2_ID]: RUN_COPPERLEAF_2_E0,
};
