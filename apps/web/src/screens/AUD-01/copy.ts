// AUD-01 copy, verbatim from the handoff spec.md and revision.md R2 (docs/screens/AUD-01.md, Copy).
// Row text (engagement names, periods, tags, initials, offices) is data, never copy. Status words
// come from the registry (`audit_engagement`), never from here.

import type { AuditDueWindow, AuditSegment, AuditTile } from "../../domain/audits";

export const COPY = {
  title: "Audits",
  noun: "audits",
  search: "Search audits",
  segmentsLabel: "Audit segments",
  segments: {
    all: "All",
    fs: "Financial statement",
    ebp: "EBP",
    review: "Review & compilation",
    soc: "SOC & IT",
    ia: "Internal audit",
  } satisfies Record<AuditSegment | "all", string>,
  chips: {
    type: "Type",
    phase: "Phase",
    partner: "Partner",
    office: "Office",
    due: "Report due",
    period: "Period",
    all: "All",
    allOffices: "All offices",
    any: "Any",
    periods: "PY2025 / FY2026",
  },
  /** The tiles, the Phase chip and the group bands: the registry's words without "{date}". */
  tiles: {
    planning: "Planning",
    fieldwork: "Fieldwork",
    in_review: "In review",
    ready_to_release: "Ready to release",
    released: "Released",
  } satisfies Record<AuditTile, string>,
  due: {
    "7d": "Next 7 days",
    "14d": "Next 14 days",
    "30d": "Next 30 days",
  } satisfies Record<AuditDueWindow, string>,
  /** "27 engagements · EBP 14 · FS audit 6 · Review 4 · Compilation/preparation 3" (+ SOC & IT,
   * Internal audit when the firm holds them, g). */
  caption: (parts: {
    total: string;
    ebp: string;
    fs: string;
    review: string;
    compilation: string;
    soc?: string;
    ia?: string;
  }) =>
    [
      `${parts.total} engagements`,
      `EBP ${parts.ebp}`,
      `FS audit ${parts.fs}`,
      `Review ${parts.review}`,
      `Compilation/preparation ${parts.compilation}`,
      ...(parts.soc === undefined ? [] : [`SOC & IT ${parts.soc}`]),
      ...(parts.ia === undefined ? [] : [`Internal audit ${parts.ia}`]),
    ].join(" · "),
  /** "Showing 27 of 27" */
  showing: (n: string, total: string) => `Showing ${n} of ${total}`,
  newAudit: "New audit",
  /** ENG-03 is planned: the button is drawn disabled with this hint outside production. */
  newAuditHint: "Not built yet",
  columns: {
    engagement: "Engagement",
    type: "Type",
    period: "Period",
    phase: "Phase",
    pbc: "PBC",
    epMgr: "EP / Mgr",
    office: "Office",
    due: "Report due",
    archive: "Archive",
  },
  /** "PLANNING · 7" (uppercase by CSS). */
  group: (phase: string, n: string) => `${phase} · ${n}`,
  /** "11 of 24" */
  pbc: (received: string, total: string) => `${received} of ${total}`,
  /** "Run 1 · started 9:24 AM by Marcus Delaney · 1 of 14 workpapers complete · blocked on a
   * partner decision" */
  run: {
    head: (n: string, time: string, by: string) => `Run ${n} · started ${time} by ${by}`,
    progress: (done: string, total: string) => `${done} of ${total} workpapers complete`,
    blocked: (role: string) => `blocked on a ${role} decision`,
  },
  archiveTooltip: (ref: string) => `Archived in the firm's tool · ${ref}`,
  noMatch: (q: string) => `No results for '${q}'.`,
  clear: "Clear filters",
  empty: "No audits yet",
  /** Visually hidden beside a report-due date. */
  dueIn: (n: number) =>
    n < 0
      ? `${String(-n)} ${-n === 1 ? "day" : "days"} past due`
      : `due in ${String(n)} ${n === 1 ? "day" : "days"}`,
  loadMore: "Load more",
  error: "Couldn’t load audits.",
} as const;
