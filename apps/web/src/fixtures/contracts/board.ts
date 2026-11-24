// F-08-T02 (DEC-5617): draft view-model types for the T19 Board kit (F-08 §5 "View models"),
// typed against by the wave-5 seed slices until K-04's C14 board contract lands, which deletes
// this file (chapter 04 §6.5). Status words are kit-local drafts until F-08-T04.
export type BoardColumnDraft = "not_started" | "in_progress" | "in_review" | "complete";
export type BoardOverlayDraft =
  "needs_input" | "waiting_on_client" | "agent_running" | "sent_back";

export interface BoardCardDraft {
  ref: string;
  title: string;
  owner: "CH" | "SB";
  column: BoardColumnDraft;
  metrics: { days: number; evidence: number; requests: number; todos: number };
  overlay?: BoardOverlayDraft;
  signoffs: { preparer: string | null; reviewer: string | null };
  /** F-08-T23: the audit area (its lane) and C-26's state ("done", "not_run", or a percent). */
  area?: string;
  agent?: "done" | "not_run" | { pct: number; running?: boolean };
  /** "2 of 4 responses" under the ID. */
  sub?: string;
}

export interface BoardDraft {
  engagement: string;
  cards: BoardCardDraft[];
  binder: { preparer: number; reviewer: number; total: number };
  /** F-08-T23: the audit-area lanes in order (Planning is collapsed, all done, no card here). */
  areas?: { key: string; title: string; phase: "planning" | "execution"; programs: number }[];
}
