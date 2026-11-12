// F-07-T04 (TPL-04; SPEC-652 AC-2, AC-4; handoff TPL-04 a–e): the Workbench chat specimen's
// scripted session on the Brightwater Hale export. Hannah Leclerc asks for TY2025 season progress
// by office at 9:21 AM; the agent's read-only discovery, the two-step question, the running tool
// cards, the result and the xlsx artifact, and the CCH Axcess token failure, as C6 v2 session
// items (`SessionItemOut`) and a `ScriptedRunSource` script for the running frame.
//
// The discovery figures are counted from the exported returns list (`e0.tax-returns.json`, 224
// TY2025 returns), never typed: 79 open + 145 done = 224; offices 98 + 64 + 62 = 224; the open
// statuses group into Gather 10 · Prepare 26 · Review 26 · Deliver 17 = 79. Engagements 214 and
// binders 241 are the handoff's words (the export holds one binder page), as is "120 of 241 · 50%".
// The eight session rows are the handoff's, owned by seed personas only (lint L10).
import type { RunItemOut, RunItemsOut, SessionItemOut } from "@abacus/api-client";
import returnsExport from "./e0.tax-returns.json";
import { stableId } from "./prng";
import type { ScriptStep } from "./tax-entity";

export type Tpl04Frame = "a" | "b" | "c" | "d" | "e";
export const TPL04_FRAMES: readonly Tpl04Frame[] = ["a", "b", "c", "d", "e"];
export const TPL04_CLOCK = "2026-09-14T09:24:00-05:00";
export const SESSION_ID = stableId("session:ty2025-season-progress");
export const RUN_ID = stableId("agent-run:ty2025-season-progress");

type Status =
  | "not_started"
  | "gathering"
  | "preparing"
  | "prepared"
  | "in_review"
  | "action_required"
  | "approved"
  | "awaiting_signature"
  | "filed"
  | "accepted";

interface ExportedReturn {
  status: Status;
  office_id: string;
  tax_year: number;
}

const RETURNS = (returnsExport as unknown as { body: { items: ExportedReturn[] } }).body.items;

/** Open and done, by the registry's tax_return words (Ready is `approved`). */
export const OPEN: readonly Status[] = [
  "not_started",
  "gathering",
  "preparing",
  "prepared",
  "in_review",
  "action_required",
  "approved",
  "awaiting_signature",
];
export const DONE: readonly Status[] = ["filed", "accepted"];
export const GROUPS = {
  Gather: ["not_started", "gathering"],
  Prepare: ["preparing", "prepared"],
  Review: ["in_review", "action_required"],
  Deliver: ["approved", "awaiting_signature"],
} as const satisfies Record<string, readonly Status[]>;

export function countBy(statuses: readonly Status[]): number {
  return RETURNS.filter((r) => statuses.includes(r.status)).length;
}

export function statusCount(status: Status): number {
  return RETURNS.filter((r) => r.status === status).length;
}

/** The export's per-office totals, largest first (the handoff names them Chicago, Denver, New York). */
export function officeTotals(): number[] {
  const by = new Map<string, number>();
  for (const r of RETURNS) by.set(r.office_id, (by.get(r.office_id) ?? 0) + 1);
  return [...by.values()].sort((a, b) => b - a);
}

export const DISCOVERY = {
  returns: RETURNS.length,
  open: countBy(OPEN),
  done: countBy(DONE),
  offices: officeTotals(),
  engagements: 214, // handoff: "214 for period 2025 (10 engagements carry two returns)"
  binders: 241, // handoff: "241 for TY2025"
  bindersRead: 120, // handoff running frame: "120 of 241 · 50%"
} as const;

export function groupTotals(): Record<keyof typeof GROUPS, number> {
  return {
    Gather: countBy(GROUPS.Gather),
    Prepare: countBy(GROUPS.Prepare),
    Review: countBy(GROUPS.Review),
    Deliver: countBy(GROUPS.Deliver),
  };
}

// --- the session list ---------------------------------------------------------------------------

export interface Tpl04Row {
  id: string;
  title: string;
  owner:
    | { kind: "human"; name: string }
    | { kind: "agent_assisted"; person: string };
  last_at: string;
  /** The meta line's relative word when not today ("Yesterday", "2 Days Ago"). */
  ago?: string;
  state: "live" | "running" | "awaiting_answer" | "ready_for_review" | "complete" | "failed";
  needs_answer: boolean;
  running: boolean;
  locked: boolean;
}

const person = (name: string) => ({ kind: "human" as const, name });
const viaAgent = (name: string) => ({ kind: "agent_assisted" as const, person: name });

export function sessionRows(frame: Tpl04Frame): Tpl04Row[] {
  const running = frame === "c";
  return [
    {
      id: SESSION_ID,
      title: "TY2025 season progress by office",
      owner: person("Hannah Leclerc"),
      last_at: "2026-09-14T14:21:00Z",
      state: running ? "running" : frame === "a" ? "awaiting_answer" : "live",
      needs_answer: frame === "a",
      running,
      locked: false,
    },
    {
      id: stableId("session:season-progress-reporter"),
      title: "Season Progress Reporter — weekly run",
      owner: viaAgent("Hannah Leclerc"),
      last_at: "2026-09-14T14:00:00Z",
      state: "complete",
      needs_answer: false,
      running: false,
      locked: false,
    },
    {
      id: stableId("session:northwind-planning"),
      title: "Run Northwind 401(k) planning workpapers",
      owner: person("Marcus Delaney"),
      last_at: "2026-09-13T15:00:00Z",
      ago: "Yesterday",
      state: "live",
      needs_answer: false,
      running: false,
      locked: false,
    },
    {
      id: stableId("session:granite-analytics"),
      title: "Granite Peak preliminary analytics",
      owner: person("Hannah Leclerc"),
      last_at: "2026-09-13T14:00:00Z",
      ago: "Yesterday",
      state: "live",
      needs_answer: false,
      running: false,
      locked: false,
    },
    {
      id: stableId("session:request-chaser"),
      title: "Request Chaser — daily",
      owner: viaAgent("Grace Holloway"),
      last_at: "2026-09-13T13:00:00Z",
      ago: "Yesterday",
      state: "complete",
      needs_answer: false,
      running: false,
      locked: false,
    },
    {
      id: stableId("session:copperleaf-payroll"),
      title: "Explain Copperleaf July→August payroll change",
      owner: person("Raj Malhotra"),
      last_at: "2026-09-12T15:00:00Z",
      ago: "2 Days Ago",
      state: "live",
      needs_answer: false,
      running: false,
      locked: false,
    },
    {
      id: stableId("session:whitley-cp2000"),
      title: "Draft CP2000 response — Whitley",
      owner: person("Kevin Osei"),
      last_at: "2026-09-11T15:00:00Z",
      ago: "3 Days Ago",
      state: "live",
      needs_answer: false,
      running: false,
      locked: false,
    },
    {
      id: stableId("session:year-end-planning"),
      title: "Year-end planning screen — 1040 clients",
      owner: person("Daniel Reyes"),
      last_at: "2026-09-09T15:00:00Z",
      ago: "5 Days Ago",
      state: "live",
      needs_answer: false,
      running: false,
      locked: false,
    },
  ];
}

// --- the thread ---------------------------------------------------------------------------------

const AT = "2026-09-14T14:21:00Z";

function item(
  seq: number,
  kind: SessionItemOut["kind"],
  payload: Record<string, unknown>,
  actor: "human" | "agent" | "system" = "agent",
): SessionItemOut {
  return {
    id: stableId(`session-item:${String(seq)}`),
    seq,
    kind,
    payload: { v: 1, ...payload },
    run_id: kind === "user_message" ? null : RUN_ID,
    step_id: null,
    actor_kind: actor,
    actor_name: actor === "human" ? "Hannah Leclerc" : null,
    created_at: AT,
  };
}

const text = (t: string) => ({ kind: "text", text: t });

export const REQUEST =
  "Build an Excel report of TY2025 tax season progress with tabs for gather, prepare, review and deliver, broken out by office.";

function discoveryBlock(): Record<string, unknown> {
  const [chicago = 0, denver = 0, newYork = 0] = DISCOVERY.offices;
  const s = statusCount;
  return {
    blocks: {
      version: 1,
      parts: [
        {
          kind: "p",
          segments: [text("I completed read-only discovery. One scope decision affects every tab.")],
        },
        { kind: "p", segments: [text("What I found in Accrued:")] },
        {
          kind: "table",
          head: ["Item", "Result"],
          rows: [
            [
              text("Tax returns"),
              text(
                `${String(DISCOVERY.returns)} for tax year 2025 (Chicago ${String(chicago)} · Denver ${String(denver)} · New York ${String(newYork)})`,
              ),
            ],
            [
              text("Return statuses"),
              text(
                `Open ${String(DISCOVERY.open)}: Not started ${String(s("not_started"))} · Gathering ${String(s("gathering"))} · Preparing ${String(s("preparing"))} · Prepared ${String(s("prepared"))} · In review ${String(s("in_review"))} · Action required ${String(s("action_required"))} · Ready ${String(s("approved"))} · Awaiting signature ${String(s("awaiting_signature"))}. Done ${String(DISCOVERY.done)}: Filed ${String(s("filed"))} · Accepted ${String(s("accepted"))}`,
              ),
            ],
            [
              text("Tax engagements"),
              text(
                `${String(DISCOVERY.engagements)} for period 2025 (10 engagements carry two returns)`,
              ),
            ],
            [text("Binders"), text(`${String(DISCOVERY.binders)} for TY2025`)],
            [text("Offices"), text("Recorded on every engagement and user: Chicago, Denver, New York")],
          ],
        },
      ],
    },
  };
}

export const QUESTION = {
  question_id: stableId("agent-question:ty2025-scope"),
  n: 1,
  m: 2,
  steps: [
    {
      q: "Which returns should the report cover?",
      preselect: "open",
      options: [
        {
          key: "open",
          title: "Open returns only",
          detail: `${String(DISCOVERY.open)} returns still in gather, prepare, review or delivery. This is what office managers act on this week.`,
        },
        {
          key: "all",
          title: "All TY2025 returns",
          detail: `All ${String(DISCOVERY.returns)} returns, including the ${String(DISCOVERY.done)} already filed or accepted.`,
        },
      ],
    },
    {
      q: "Where should I save the workbook?",
      preselect: "files",
      options: [{ key: "files", title: "Files › Firm reports › TY2025 season" }],
    },
  ],
  skipText: "Skip",
  skipDefault: "open",
};

function toolCard(seq: number, label: string, state: "succeeded" | "running" | "failed") {
  return item(seq, "tool_card", { label, state });
}

function progress(seq: number): SessionItemOut {
  const pct = Math.round((DISCOVERY.bindersRead / DISCOVERY.binders) * 100);
  return item(seq, "tool_card", {
    label: "Gathering the records",
    state: "running",
    counters: [
      { label: "Returns", state: "succeeded", value: String(DISCOVERY.open) },
      { label: "Engagements", state: "succeeded", value: String(DISCOVERY.engagements) },
      {
        label: "Binders",
        state: "running",
        value: `${String(DISCOVERY.bindersRead)} of ${String(DISCOVERY.binders)} · ${String(pct)}%`,
      },
    ],
  });
}

function result(seq: number): SessionItemOut {
  const g = groupTotals();
  return item(seq, "agent_blocks", {
    badge: "Report prepared",
    blocks: {
      version: 1,
      parts: [
        {
          kind: "p",
          segments: [
            text(
              `Season progress, open returns: Gather ${String(g.Gather)} · Prepare ${String(g.Prepare)} · Review ${String(g.Review)} · Deliver ${String(g.Deliver)}`,
            ),
          ],
        },
      ],
    },
  });
}

export const ARTIFACT = {
  artifact_id: stableId("artifact:ty2025-season-progress-xlsx"),
  name: "TY2025 Season Progress — by office.xlsx",
  meta: "Excel · 5 tabs",
};

export function threadItems(frame: Tpl04Frame): SessionItemOut[] {
  if (frame === "b") return []; // WB-02: a new session
  const base = [
    item(1, "user_message", { body: REQUEST }, "human"),
    item(2, "agent_blocks", {
      blocks: {
        version: 1,
        parts: [
          {
            kind: "p",
            segments: [
              text(
                "I'll start with read-only discovery of returns, engagements, binders and offices.",
              ),
            ],
          },
        ],
      },
    }),
    item(3, "agent_blocks", discoveryBlock()),
  ];
  if (frame === "a") return [...base, item(4, "question", QUESTION)];
  const answered = [
    ...base,
    item(4, "question", QUESTION),
    item(5, "answer", { answers_seq: 4, key: "open", title: "Open returns only" }, "human"),
    toolCard(6, `Execute › Read ${String(DISCOVERY.open)} open returns`, "succeeded"),
  ];
  if (frame === "c") {
    return [
      ...answered,
      toolCard(7, "Execute › Build gather / prepare / review / deliver tabs", "running"),
      progress(8),
    ];
  }
  if (frame === "e") {
    return [
      ...answered,
      item(7, "tool_card", {
        label: "Read binder status",
        state: "failed",
        error: { title: "Stopped at Read binder status", body: "CCH Axcess token expired on Sep 12." },
      }),
    ];
  }
  return [
    ...answered,
    toolCard(7, "Execute › Build gather / prepare / review / deliver tabs", "succeeded"),
    result(8),
    item(9, "artifact", ARTIFACT),
  ];
}

export const SUGGESTED_PROMPTS = [
  "Status report by office",
  "Tie the trial balance to the ledger",
  "Explain a year-over-year change",
  "Planning screen for 1040 clients",
] as const;
export const CONTEXT_CHIPS = ["Client record", "Documents", "Workpapers"] as const;

// --- the running frame's script (ScriptedRunSource) -----------------------------------------------

function runItem(seq: number, detail: string, outcome: "succeeded" | null): RunItemOut {
  return {
    seq,
    kind: "tool_card",
    at: AT,
    code: "execute",
    outcome,
    detail,
    actor: null,
    ref_type: null,
    ref_id: null,
  };
}

/** TPL-04c → d: the tool cards tick, then the tabs build; `?static=1` freezes on the last page. */
export function tpl04Script(): ScriptStep[] {
  const items = [
    runItem(1, `Read ${String(DISCOVERY.open)} open returns`, "succeeded"),
    runItem(2, "Build gather / prepare / review / deliver tabs", null),
    runItem(3, "Build gather / prepare / review / deliver tabs", "succeeded"),
  ];
  const page = (upto: number, state: "running" | "succeeded"): RunItemsOut => ({
    run: {
      id: RUN_ID,
      agent: "runtime.conformance",
      agent_label: "TY2025 season progress by office",
      state,
      started_at: AT,
      finished_at: state === "succeeded" ? "2026-09-14T14:23:41Z" : null,
      duration_ms: state === "succeeded" ? 161_000 : null,
      initiator_name: "Hannah Leclerc",
      subject: null,
    },
    items: items.slice(0, upto),
    last_seq: upto,
    next_seq: upto,
    resync: false,
  });
  return [
    { page: page(2, "running"), afterMs: 0 },
    { page: page(3, "succeeded"), afterMs: 800 },
  ];
}
