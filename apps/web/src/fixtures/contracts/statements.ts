// F-08-T27 (DEC-6025): draft view-model types for the T20 document editor and the TPL-22 specimen
// (F-08 §5 "View models"), until R-01's statements-studio contract lands and deletes this file.
// Values are computed by code (ADR-050): a line's figure is its TB groups' sum, its formula over
// other lines, or a person's override; the editor only ever shows them.

export type LineSource = "tb_linked" | "formula" | "override";

export interface TbGroupDraft {
  label: string;
  account: string;
  amount: number;
}

export interface LineItemDraft {
  key: string;
  caption: string;
  indent: 0 | 1 | 2;
  /** The figure for each year shown, keyed "2026" and "2025". */
  amounts: Record<"2026" | "2025", number>;
  source: LineSource;
  /** tb_linked: the groups whose sum is the 2026 figure. */
  groups?: TbGroupDraft[];
  /** formula: the line keys summed (a leading "-" subtracts). */
  formula?: string[];
  /** override: a person's figure and, when stale, what the linked groups now total. */
  override?: { value: number; linkedNow: number | null; reason: string };
  rule?: "above" | "double_below";
  dollar?: boolean;
}

export interface StatementPageDraft {
  page: number;
  key: string;
  title: string;
  tie: boolean | null;
  linked: boolean;
}

export interface TocRowDraft {
  key: string;
  label: string;
  pages: string | null;
  status: "done" | "partly" | "none";
  pill: string | null;
  linked: boolean;
  children?: string[];
  commentCount?: number;
  presence?: string[];
}

export interface TieOutRunDraft {
  run: number;
  at: string;
  total: number;
  differences: number;
  staleOverrides: number;
}

export interface PresenceDraft {
  person: string;
  initials: string;
  doing: "editing" | "viewing";
  where: string;
}

export interface CommentDraft {
  author: string;
  at: string;
  body: string;
  citations: number;
}

export interface StatementsDraft {
  engagement: string;
  methodology: string;
  stage: string;
  documentTitle: string;
  entity: string;
  periodLine: string;
  pageCount: number;
  /** The pages the handoff places (FSP-01: balance sheets p. 3, cash flows p. 6, Note 9 p. 13). */
  pages: StatementPageDraft[];
  toc: TocRowDraft[];
  balanceSheet: LineItemDraft[];
  usedIn: { label: string; amount: number | null; formula?: string }[];
  priorYearSource: { file: string; page: number; at: string };
  rollForward: { step: string; done: string }[];
  tieOuts: TieOutRunDraft[];
  relinks: { line: string; by: string; at: string; from: number; to: number; cause: string }[];
  presence: PresenceDraft[];
  previouslyViewed: { person: string; at: string }[];
  comments: {
    anchor: string;
    page: number;
    resolvedBy: string;
    resolvedAt: string;
    thread: CommentDraft[];
  };
  note9: {
    page: number;
    inserted: string;
    kept: string;
    struck: string;
    acceptedBy: string;
    acceptedAt: string;
    attribution: string;
    sources: string[];
  };
  share: { access: string; with: string; at: string };
}
