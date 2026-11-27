// K-03-T09 (TASK-8853): the SH-1 fixture slice for SHT-01, SHT-02 and SHT-04, typed by the sheets
// contract (C23) and built from the F-08-T02 SURL seed (granite-peak-fy2026-surl-sheet). The strata
// foot 24 + 16 = 40 rows and 3,286,400.00 + 412,300.00 = 3,698,700.00; the status-bar conclusions
// 31 + 8 + 1 + 0 = 40 (SHT-01 spec). sheets-sh1.foot.test.ts re-adds them (ADR-050).
import type {
  AgentColumnOut,
  AgentRunOut,
  CitationV2Out,
  RunViewOut,
  SheetRowDetailOut,
  SheetRowFactOut,
  SheetRowOut,
  SheetVmOut,
} from "@abacus/api-client";
import { amount } from "@abacus/ui";
import { SURL_SHEET } from "./granite-peak-fy2026-surl-sheet";
import { stableId } from "./prng";
import drawer from "./scenario.sht01-drawer.json";

export const SHEET_ID = stableId("sheet:granite-peak:bh-fs-430");
const WORK_ITEM = stableId("work-item:granite-peak:bh-fs-430");
export const CONCLUSIONS = {
  properly_excluded: 31,
  properly_included: 8,
  improperly_excluded: 1,
  needs_input: 0,
};

const COLUMNS: SheetVmOut["columns"] = [
  ["key", "text", "Key", 96, true],
  ["vendor", "text", "Vendor", 220],
  ["paid_on", "date", "Paid", 110],
  ["amount", "currency", "Amount", 120],
  ["invoice_on", "date", "Invoice date", 110],
  ["service_period", "text", "Service period", 120],
  ["recorded_in", "text", "Recorded in", 110],
  ["conclusion", "agent", "Conclusion", 200],
].map(([key, type, label, width, frozen]) => ({
  column_id: stableId(`sheet-column:${String(key)}`),
  key: String(key),
  type: type as SheetVmOut["columns"][number]["type"],
  label: String(label),
  width: Number(width),
  frozen: frozen === true,
  ...(key === "conclusion" ? { agent_name: "Conclusion" } : {}),
  options: [],
}));

const money = (n: number): string => amount(n, "cents").text;

export type SheetVariant = "default" | "empty" | "filled" | "running" | "locked";

export function sheet(variant: SheetVariant = "default"): SheetVmOut {
  const empty = variant === "empty";
  return {
    sheet_id: SHEET_ID,
    work_item_id: WORK_ITEM,
    title: SURL_SHEET.procedure,
    columns: COLUMNS,
    sections: SURL_SHEET.sections.map((s) => ({
      key: s.key,
      title: s.title,
      count: empty ? 0 : s.count,
      total: empty ? null : money(s.total),
    })),
    status: {
      rows: empty ? 0 : SURL_SHEET.status.rows,
      exceptions: empty || variant === "filled" ? 0 : SURL_SHEET.status.exceptions,
      view: "Default",
      agent_running: variant === "running",
      agent_summary:
        variant === "running"
          ? "11 tested · 3 running · 26 waiting"
          : variant === "default"
            ? "40 suggestions not yet adopted"
            : null,
    },
    signed_off: variant === "locked",
    allowed_actions: variant === "locked" ? [] : ["edit", "configure", "run_agent_column"],
  };
}

export function rows(variant: SheetVariant = "default"): SheetRowOut[] {
  if (variant === "empty") return [];
  return SURL_SHEET.rows.map((r, i) => ({
    row_id: stableId(`sheet-row:${r.key}`),
    key: r.key,
    section_key: r.sectionKey,
    locked: variant === "locked",
    version: 1,
    cells: {
      key: { value: r.key, state: "human" as const },
      vendor: { value: r.vendor, state: "human" as const },
      paid_on: { value: r.paidOn, state: "human" as const },
      amount: { value: money(r.amount), state: "human" as const },
      invoice_on: { value: r.invoiceOn, state: "human" as const },
      service_period: { value: r.servicePeriod, state: "human" as const },
      recorded_in: { value: r.recordedIn, state: "human" as const },
      conclusion:
        variant === "filled"
          ? { value: "", state: "empty" as const }
          : {
              value: r.conclusion.value,
              state: "suggested" as const,
              exception: r.conclusion.value === "improperly_excluded" && i >= 0,
            },
    },
  }));
}

export function agentColumn(status: AgentColumnOut["status"]): AgentColumnOut {
  return {
    column_id: stableId("sheet-column:conclusion"),
    instruction:
      "Compare @Invoice date and @Service period with the period end 6/30/2026 and @Recorded in; conclude Properly excluded, Properly included, Improperly excluded or Needs input.",
    mention_refs: ["invoice_on", "service_period", "recorded_in"],
    output_type: "single_select",
    options: [
      { value: "properly_excluded", label: "Properly excluded" },
      { value: "properly_included", label: "Properly included" },
      { value: "improperly_excluded", label: "Improperly excluded" },
      { value: "needs_input", label: "Needs input" },
    ],
    default_scope: "empty_only",
    status,
    saved_by: status === "saved" ? "Hannah Leclerc" : null,
    saved_at: status === "saved" ? "2026-09-25T14:31:00-05:00" : null,
  };
}

// ---- K-03-T22 (DEC-6033): SHT-01 e, the row drawer on SURL-05 ----------------------------------
// The drawer's facts, the agent's reason, its two sources, its run and its evidence link are the
// Python scenario's (`seed/scenario.sht01-drawer.json`, `make fixtures`, never hand written).

export const DRAWER_ROW_KEY = drawer.row_key;
export const DRAWER_RUN_ID = stableId("agent-run:granite-peak:surl-tester:2026-09-28");
const DRAWER_EVIDENCE = stableId("evidence-version:granite-peak:frf-30418");
const ENGAGEMENT = stableId("engagement:granite-peak:fy2026");

function drawerRow(): SheetRowOut {
  const found = rows("default").find((r) => r.key === drawer.row_key);
  if (found === undefined) throw new Error(`no ${drawer.row_key} in the SH-1 slice`);
  return found;
}

export function rowDrawer(): SheetRowDetailOut {
  return {
    engagement_id: ENGAGEMENT,
    row: drawerRow(),
    facts: drawer.facts.map((f) => ({ ...f, type: f.type as SheetRowFactOut["type"] })),
    why: [
      {
        column_key: "conclusion",
        suggestion_id: stableId(`suggestion:${drawer.row_key}:conclusion`),
        status: "pending",
        version: 1,
        rationale: drawer.rationale,
        citation_count: drawer.citations.length,
        agent_run_id: DRAWER_RUN_ID,
      },
    ],
    links: [
      {
        kind: "evidence",
        target_id: DRAWER_EVIDENCE,
        linked_at: drawer.evidence.linked_at,
        label: drawer.evidence.label,
      },
    ],
  };
}

export function rowDrawerCitations(): CitationV2Out[] {
  return drawer.citations.map((c, i) => ({
    id: stableId(`citation:${drawer.row_key}:conclusion:${String(i + 1)}`),
    n: i + 1,
    kind: c.kind as CitationV2Out["kind"],
    title: c.title,
    loc: c.loc,
    // The handoff names both sources without their text: withheld, never invented.
    quote: null,
    quote_state: "withheld",
    value_text: null,
    match_id: null,
    state: "valid",
    verified: true,
    verification_reason: null,
    created_by: { kind: "agent", label: "Accrued Agent" },
    retrieved_at: drawer.agent.finished_at,
    used_in: 1,
    moved: null,
    allowed_actions: [],
    source: {
      type: c.kind === "document_text" ? "evidence_version" : "record",
      id: c.kind === "document_text" ? DRAWER_EVIDENCE : stableId(`record:${c.title}`),
      version: "1",
      evidence_version_id: c.kind === "document_text" ? DRAWER_EVIDENCE : null,
      page: c.kind === "document_text" ? 1 : null,
    },
  }));
}

export function rowDrawerRun(): RunViewOut {
  return {
    projection: "metadata",
    allowed_actions: [],
    run: drawerRun(),
    run_record_sha256: `sha256:${"0".repeat(64)}`,
  };
}

function drawerRun(): AgentRunOut {
  return {
    id: DRAWER_RUN_ID,
    agent: "workpapers.column_filler",
    agent_label: drawer.agent.label,
    initiator_name: "Cole Hart",
    subject: drawer.row_key,
    state: "succeeded",
    stage: "live",
    started_at: drawer.agent.started_at,
    finished_at: drawer.agent.finished_at,
    duration_ms: 300_000,
  };
}
