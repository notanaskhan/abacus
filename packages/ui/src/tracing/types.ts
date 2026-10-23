// E1 MatchProvider and C-07 Cite kit shapes (F-05-T41; plan 04 §4.3 E1, E2; contract C4,
// docs/contracts/c04-citations-viewer.md §3.1). Generic view models: a screen maps a C4 citation or
// a cell it draws into these; nothing here imports the API client.
//
// INV-2 (ADR-066): a match id comes from a typed locator, never from model text. The `MatchId`
// brand makes that a type rule. Two functions mint it: `matchIdOf(locator)`, which derives the id
// from a C4 locator exactly as the server does (for a cell or row the page draws itself), and
// `contractMatchId(citation)`, which takes the server's `match_id` off a typed C4 citation or
// region. Everything that lights takes a `MatchId`, so a string from a model cannot reach
// `data-match` without a cast a reviewer would see.

declare const MATCH_ID: unique symbol;

/** An opaque id carried in `data-match`. Mint it with `matchIdOf` or `contractMatchId`. */
export type MatchId = string & { readonly [MATCH_ID]: true };

/** C4's locator kinds (§3.1), with the fields the match id is derived from. */
export type Locator =
  | {
      kind: "document_text";
      evidence_version_id: string;
      page: number;
      /** `[x0, top, x1, bottom]` in page points. */
      bbox?: readonly [number, number, number, number] | null;
    }
  | {
      kind: "sheet_cell";
      /** The workbook's file name: the id is `<file>!<cell>`. */
      file: string;
      sheet: string;
      /** A cell ("D8") or a range ("D6:D7"). */
      cell: string;
    }
  | { kind: "ledger_line"; ledger_snapshot_id: string; account_code: string }
  | { kind: "workpaper_cell"; sheet_id: string; row_key: string; column_key: string }
  | { kind: "methodology_step"; template_version_id: string; step_key: string }
  | { kind: "policy_rule"; threshold_policy_id: string; version: number; rule_key: string }
  | { kind: "record_field"; record_type: string; record_id: string; field: string }
  | { kind: "tax_form_line"; return_id: string; form: string; line: string }
  | { kind: "artifact_cell"; run_artifact_id: string; cell: string }
  | { kind: "request_item"; request_item_id: string };

export type LocatorKind = Locator["kind"];

/** A typed C4 citation or region: its server-derived `match_id` and the kind it was derived for. */
export interface ContractMatch {
  kind: LocatorKind;
  match_id: string;
}

/** How an element joins a match: rows, cells and regions light after 120ms, markers after 150ms. */
export type MatchKind = "row" | "cell" | "region" | "marker";

/** A citation as the C-07 marker, popover and chip draw it. */
export interface CitationView {
  /** The marker number. */
  n: number;
  /** The source's name: the popover's title (rendered by code from the locator, C4 §3.2). */
  title: string;
  /** The exact source text. */
  quote: string;
  /** Where in the source: always shown ("Investments!D8", "Page 3"). */
  loc: string;
  /** What it lights; null when nothing on the page carries it (the popover anchors to the
   * marker and nothing else lights). */
  match: MatchId | null;
  /** The dialog button the source takes (Open in Excel, Open PDF, Open in Word, Open workpaper). */
  kind?: "xlsx" | "pdf" | "docx" | "workpaper";
}

/** What the anchored popover shows: a list of citations and the one in view. */
export interface CitationPayload {
  list: readonly CitationView[];
  index: number;
}
