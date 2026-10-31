// HOME-02's evidence summaries (I-01-T18; I-01 §3 F7, AC7.7; docs/screens/HOME-02.md): the shape
// of what a gate's owner shows beside the detail when the evidence is a computed statement rather
// than a document: a TallyStrip, a statement table with the row the decision turns on lit in the
// match purple, a calc card, a proposed-fix callout, a paper (the preparer memo), or the cited
// items of a source. The owner computes every figure (code computes, ADR-050); HOME-02 lays them
// out and computes nothing. Tax summaries are fixture-only until T-05 (DV-4): no owner serves one
// yet, so a live gate shows its cited sources alone. The shape lives in app-core because both the
// fixtures (which supply it) and the screen (which lays it out) read it; domain/home re-exports it.

import type { PillVariant, TallyItem } from "@abacus/ui";

export interface EvidenceCell {
  text: string;
  /** A pill in place of the text ("Reconciled ✓", "off 28,595"). */
  pill?: { variant: PillVariant; check?: boolean };
  /** The figure the decision turns on, in match ink. */
  match?: boolean;
  /** A negative shown in brackets, red ink. */
  negative?: boolean;
}

export interface EvidenceRow {
  cells: readonly EvidenceCell[];
  /** The row lit in the match purple (the cited region's row). */
  lit?: boolean;
  /** A total or result row: 500 weight over a rule. */
  total?: boolean;
}

export interface EvidenceTable {
  /** The table's accessible name. */
  label: string;
  /** The first column reads left; the rest are figures, right-aligned. */
  columns: readonly string[];
  rows: readonly EvidenceRow[];
}

export interface EvidenceCalcLine {
  label: string;
  value: string;
  result?: boolean;
}

export interface EvidenceSummary {
  /** The pane header: "Basis at 12/31/2025 · Ridgeline". */
  title: string;
  /** The summary's option in the small segmented ("Basis"). */
  segment: string;
  /** "Open in workpaper ↗" / "Open memo ↗": a planned link (TXP-08, TXP-01). */
  planned?: string;
  tally?: readonly TallyItem[];
  /** A pill after the strip ("off 28,595"). */
  aside?: { text: string; variant: PillVariant };
  table?: EvidenceTable;
  calc?: { lines: readonly EvidenceCalcLine[]; note?: string };
  /** The agent's proposed fix: who proposed and who it waits on, and its words (AgentText). */
  proposal?: { by: string; text: string };
  paper?: { title: string; byline: string; paragraphs: readonly string[] };
  cited?: { title: string; items: readonly string[] };
  /** Short segment labels for the gate's cited sources, by evidence version ("Transfer agreement"). */
  sources?: Readonly<Record<string, string>>;
}

/** Where a host finds a gate's summary (fixtures and, later, the owners' reads). */
export type EvidenceSummaryOf = (gateSubjectId: string) => EvidenceSummary | undefined;
