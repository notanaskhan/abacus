// W-02-T02 (TASK-7604; SPEC-653; docs/contracts/workbench-sessions.md): the workbench-sessions
// family's E0 fixtures, one per artboard that reads it: WB-01 a–g (the list, its filters, counts,
// search and the locked row), WB-02 a–f (blank create, the picker's three tabs, the attached
// context), WB-03 d and d2 (the drill and the O4 preview). Thread items for WB-01 a–e and WB-03's
// run arc are C6 v2 session items (`tpl04-sessions.ts`, W-02-T13's scenarios); this file holds
// only the family's own payloads.
//
// Figures are counted from the exported returns (`e0.tax-returns.json`), never typed: the office ×
// stage matrix of WB-03 d2 and the 11 "Action required" returns of the drill are computed here and
// must foot to the handoff's 34 + 23 + 22 = 10 + 26 + 26 + 17 = 79. Rows are the handoff's eight,
// owned by seed personas (lint L10). No row of a client the viewer can't open carries a figure.
import type {
  ArtifactPreviewOut,
  ContextItemsOut,
  ContextOptionsOut,
  DrillOut,
  SessionListOut,
  SessionSummaryOut,
} from "@abacus/api-client";
import returnsExport from "./e0.tax-returns.json";
import { stableId } from "./prng";
import { GROUPS, sessionRows } from "./tpl04-sessions";

export const WB_CLOCK = "2026-09-14T09:24:00-05:00";
export const WB02_CLOCK = "2026-09-14T14:40:00-05:00";

type Status = (typeof GROUPS)[keyof typeof GROUPS][number] | "filed" | "accepted";
interface ExportedReturn {
  id: string;
  client_name: string;
  form: string;
  status: Status;
  office_id: string;
  preparer: { name: string } | null;
}
const RETURNS = (returnsExport as unknown as { body: { items: ExportedReturn[] } }).body.items;

/** Offices by size, named as the handoff names them (98 · 64 · 62). */
export function offices(): { id: string; name: "Chicago" | "Denver" | "New York" }[] {
  const by = new Map<string, number>();
  for (const r of RETURNS) by.set(r.office_id, (by.get(r.office_id) ?? 0) + 1);
  const names = ["Chicago", "Denver", "New York"] as const;
  return [...by.entries()].sort((a, b) => b[1] - a[1]).map(([id], i) => ({ id, name: names[i]! }));
}

// --- WB-01: the list --------------------------------------------------------------------------

export type WbListScenario =
  | "wb01-list-e0"
  | "wb01c-running-three"
  | "wb01c-running-four"
  | "wb01e-request-chaser-failed"
  | "wb01f-search-k3"
  | "wb01g-locked-copperleaf";

const HANNAH = stableId("user:hannah-leclerc");

function row(
  r: ReturnType<typeof sessionRows>[number],
  extra: Partial<SessionSummaryOut> = {},
): SessionSummaryOut {
  const via = r.owner.kind === "agent_assisted";
  const name = r.owner.kind === "human" ? r.owner.name : r.owner.person;
  return {
    id: r.id,
    title: r.title,
    state: r.state,
    last_item_at: r.last_at,
    owner: { user_id: name === "Hannah Leclerc" ? HANNAH : null, name, via_agent: via },
    origin: via ? "schedule" : "manual",
    agent_label: via ? r.title.split(" — ")[0]! : null,
    needs_answer: r.needs_answer,
    running: r.running,
    ready_for_review: r.state === "ready_for_review",
    locked: r.locked,
    title_source: "auto",
    version: "1",
    ...extra,
  };
}

/** WB-01 a at 9:24 AM for Hannah: the eight rows; row 1 needs her answer, row 2 is ready for
 * review; row 6 (Copperleaf, a client she can't open) is listed with metadata only and locked. */
export function e0Rows(): SessionSummaryOut[] {
  const rows = sessionRows("a");
  return rows.map((r, i) => {
    if (i === 0) return row(r, { state: "awaiting_answer", needs_answer: true });
    if (i === 1) return row(r, { state: "ready_for_review", ready_for_review: true });
    if (r.title.startsWith("Explain Copperleaf")) return row(r, { locked: true });
    return row(r);
  });
}

const CLOSE_RUNS = [
  {
    key: "copperleaf-close",
    title: "Copperleaf Coffee Roasters — August 2026 close, Run 2",
    at: "2026-09-14T14:06:00Z",
    person: "Raj Malhotra",
  },
  {
    key: "cedar-hollow-close",
    title: "Cedar Hollow Farms — August 2026 close",
    at: "2026-09-14T13:52:00Z",
    person: "Ezra Gold",
  },
  {
    key: "hollis-creek-close",
    title: "Hollis Creek Veterinary — August 2026 close",
    at: "2026-09-14T14:12:00Z",
    person: "Erin Walsh",
  },
] as const;

function closeRow(c: (typeof CLOSE_RUNS)[number], locked: boolean): SessionSummaryOut {
  return {
    id: stableId(`session:${c.key}`),
    title: c.title,
    state: "running",
    last_item_at: c.at,
    owner: { user_id: null, name: c.person, via_agent: true },
    origin: "engagement_run",
    agent_label: "Closing agent",
    needs_answer: false,
    running: true,
    ready_for_review: false,
    locked,
    title_source: "auto",
    version: "1",
  };
}

/** Run #4127 (Northwind, Hannah's) is Dispatched at 9:24:00 and Running from 9:25 (AC-L2). */
const RUN_4127_ROW: SessionSummaryOut = {
  id: stableId("session:northwind-run-4127"),
  title: "Run Northwind 401(k) planning workpapers",
  state: "running",
  last_item_at: "2026-09-14T14:25:00Z",
  owner: { user_id: null, name: "Marcus Delaney", via_agent: true },
  origin: "engagement_run",
  agent_label: "Engagement agent",
  needs_answer: false,
  running: true,
  ready_for_review: false,
  locked: false,
  title_source: "auto",
  version: "1",
};

export function wbList(scenario: WbListScenario): SessionListOut {
  switch (scenario) {
    case "wb01-list-e0":
    case "wb01g-locked-copperleaf": {
      const items = e0Rows();
      return { items, total: items.length, counts: { running: 0, needs_answer: 1 } };
    }
    case "wb01c-running-three": {
      // Margaret Okonkwo can open every client: nothing locked; Needs your answer 0.
      const items = CLOSE_RUNS.map((c) => closeRow(c, false));
      return { items, total: items.length, counts: { running: 3, needs_answer: 0 } };
    }
    case "wb01c-running-four": {
      const items = [RUN_4127_ROW, ...CLOSE_RUNS.map((c) => closeRow(c, false))];
      return { items, total: items.length, counts: { running: 4, needs_answer: 0 } };
    }
    case "wb01e-request-chaser-failed": {
      const items = e0Rows().map((r) =>
        r.title === "Request Chaser — daily" ? { ...r, state: "failed" as const } : r,
      );
      return { items, total: items.length, counts: { running: 0, needs_answer: 1 } };
    }
    case "wb01f-search-k3":
      return { items: [], total: 0, counts: { running: 0, needs_answer: 1 } };
  }
}

/** WB-01 g: the locked session's contacts (the screen's copy names them; no figure). */
export const LOCKED_CONTACTS = ["Raj Malhotra", "Priya Raman"] as const;
export const LOCKED_CLIENT = "Copperleaf Coffee Roasters, Inc.";

// --- WB-02: the blank session and the context picker --------------------------------------------

export const NEW_SESSION: SessionSummaryOut = {
  id: stableId("session:new-northwind-question"),
  title: "New session",
  state: "live",
  last_item_at: "2026-09-14T19:40:00Z",
  owner: { user_id: HANNAH, name: "Hannah Leclerc", via_agent: false },
  origin: "manual",
  agent_label: null,
  needs_answer: false,
  running: false,
  ready_for_review: false,
  locked: false,
  title_source: "auto",
  version: "1",
};

const NORTHWIND_PLAN = stableId("client-entity:northwind-401k-plan");
const PBC = stableId("request-set:northwind-py2025-pbc");
const PLANNING = stableId("workpaper-set:northwind-py2025-planning");

/** The picker (WB-02 b): only records Hannah can open; Copperleaf is never listed (AC-C3). */
export function contextOptions(
  tab: ContextOptionsOut["tab"],
  attached: readonly string[] = [],
): ContextOptionsOut {
  const on = (id: string) => attached.includes(id);
  const items: ContextOptionsOut["items"] =
    tab === "client_record"
      ? [
          {
            kind: "client_entity",
            ref_id: NORTHWIND_PLAN,
            title: "Northwind Robotics 401(k) Plan",
            detail: "Plan · PY2025 EBP Audit · Chicago",
          },
          {
            kind: "client",
            ref_id: stableId("client:northwind-robotics"),
            title: "Northwind Robotics, Inc.",
            detail: "Plan sponsor",
          },
          {
            kind: "client",
            ref_id: stableId("client:granite-peak"),
            title: "Granite Peak Outdoor Supply, Inc.",
            detail: "C corp · FY2026 FS audit · Denver",
          },
          {
            kind: "client",
            ref_id: stableId("client:lakeshore-literacy"),
            title: "Lakeshore Literacy Alliance",
            detail: "501(c)(3) · FY2026 SSARS review",
          },
        ]
      : tab === "documents"
        ? [
            {
              kind: "request_set",
              ref_id: PBC,
              title: "PY2025 EBP Audit · PBC requests",
              detail: "12 of 24 received",
            },
            {
              kind: "document",
              ref_id: stableId("document:paygrid-contribution-detail-2025"),
              title: "PayGrid Contribution Detail 2025.xlsx",
            },
            {
              kind: "document",
              ref_id: stableId("document:keystone-account-balances-py2025"),
              title: "Keystone Account Balances PY2025.xlsx",
            },
            {
              kind: "document",
              ref_id: stableId("document:harborline-net-trust-assets-2025"),
              title: "Harborline Summary of Net Trust Assets 12/31/2025.pdf",
            },
          ]
        : [
            {
              kind: "workpaper_set",
              ref_id: PLANNING,
              title: "PY2025 planning workpapers",
              detail: "Trial Balance · Materiality v2 · Internal Control",
            },
            {
              kind: "workpaper_set",
              ref_id: stableId("workpaper-set:northwind-py2024-archived"),
              title: "PY2024 audit file (archived)",
            },
          ];
  return { tab, items: items.map((i) => ({ ...i, attached: on(i.ref_id) })) };
}

/** WB-02 b's three checked rows, one per tab. */
export const PICKED = [NORTHWIND_PLAN, PBC, PLANNING] as const;

/** WB-02 c/d: the attached items with their code-computed summary lines (AC-C4). */
export function attachedContext(): ContextItemsOut {
  return {
    session_id: NEW_SESSION.id,
    firm_wide: false,
    items: [
      {
        id: stableId("context-item:northwind-plan"),
        kind: "client_entity",
        ref_id: NORTHWIND_PLAN,
        card_title: "Client record",
        chip_label: "Northwind Robotics 401(k) Plan",
        summary_lines: [
          "Northwind Robotics 401(k) Plan · PN 001 · plan year Jan 1–Dec 31 · 286 participants with balances at BOY",
        ],
      },
      {
        id: stableId("context-item:northwind-pbc"),
        kind: "request_set",
        ref_id: PBC,
        card_title: "Documents",
        chip_label: "PBC · 12 of 24",
        summary_lines: ["24 requests · 12 received · 3 files in use"],
      },
      {
        id: stableId("context-item:northwind-planning"),
        kind: "workpaper_set",
        ref_id: PLANNING,
        card_title: "Workpapers",
        chip_label: "Planning workpapers",
        summary_lines: [
          "Trial Balance · Prepared · MD · Materiality v2 · $252,200 · Internal Control · 7 exceptions",
        ],
      },
    ],
  };
}

/** WB-02 a and f: the blank session's context, firm-wide and read-only. */
export const FIRM_WIDE: ContextItemsOut = {
  session_id: NEW_SESSION.id,
  firm_wide: true,
  items: [],
};

// --- WB-03 d and d2: the drill and the O4 preview ----------------------------------------------

export const ARTIFACT_ID = stableId("run-artifact:ty2025-season-progress-by-office");
export const ARTIFACT_NAME = "TY2025 Season Progress — by office.xlsx";
const STAGES = ["Gather", "Prepare", "Review", "Deliver"] as const;

/** The Summary tab's office × stage matrix, counted from the export (AC-R2). */
export function summaryMatrix(): { office: string; cells: number[]; total: number }[] {
  const out = offices().map(({ id, name }) => {
    const cells = STAGES.map(
      (s) =>
        RETURNS.filter(
          (r) => r.office_id === id && (GROUPS[s] as readonly string[]).includes(r.status),
        ).length,
    );
    return { office: name, cells, total: cells.reduce((a, b) => a + b, 0) };
  });
  const cells = STAGES.map((_, i) => out.reduce((a, r) => a + r.cells[i]!, 0));
  return [...out, { office: "Total", cells, total: cells.reduce((a, b) => a + b, 0) }];
}

const WORD: Record<string, string> = {
  not_started: "Not started",
  gathering: "Gathering",
  preparing: "Preparing",
  prepared: "Prepared",
  in_review: "In review",
  action_required: "Action required",
  approved: "Ready",
  awaiting_signature: "Awaiting signature",
};

/** The d2 stage-definition row, counted ("Gather = Not started 2 + Gathering 8 · …"). */
export function stageDefinition(): string {
  return STAGES.map(
    (s) =>
      `${s} = ${GROUPS[s]
        .map((code) => `${WORD[code]!} ${String(RETURNS.filter((r) => r.status === code).length)}`)
        .join(" + ")}`,
  ).join(" · ");
}

const n = (v: number) => ({ value: String(v), kind: "number" as const });

export function artifactPreview(sheet = "Summary"): ArtifactPreviewOut {
  return {
    artifact_id: ARTIFACT_ID,
    file_name: ARTIFACT_NAME,
    sheets: ["Summary", ...STAGES],
    sheet,
    columns: ["Office", ...STAGES, "Total"],
    rows: summaryMatrix().map((r) => [
      { value: r.office, kind: "text" as const, bold: r.office === "Total" },
      ...r.cells.map(n),
      { ...n(r.total), bold: true },
    ]),
    footnote: stageDefinition(),
    // The stored artifact's digest in fixture mode (the live preview reads the stored bytes).
    sha256: "5d1f0c8e7a2b4c6d9e0f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f7",
  };
}

/** WB-03 d: "Action required 11" drilled: the 11 returns, by client name, linked to TAX-02. */
export function actionRequiredDrill(): DrillOut {
  const rows = RETURNS.filter((r) => r.status === "action_required")
    .sort((a, b) => a.client_name.localeCompare(b.client_name))
    .map((r) => ({
      ref_type: "tax_return" as const,
      ref_id: r.id,
      label: r.client_name,
      detail: [r.form, r.preparer?.name].filter(Boolean).join(" · "),
      href: `/tax-returns/${r.id}`,
    }));
  return {
    item_id: stableId("session-item:drill-action-required"),
    group_key: "status:action_required",
    title: "Action required",
    total: rows.length,
    rows,
  };
}
