// F-08-T02 (DEC-5617): draft view-model types for the T18 Sheet kit (F-08 §5 "View models"),
// typed against by the wave-5 seed slices until K-03's sheets contract lands, which deletes this
// file (chapter 04 §6.5). Cell status words are the generated `sheet_cell` codes (F-08-T04).
import type { SheetCellState } from "@abacus/ui";

export type { SheetCellState };
export type SurlConclusion = "properly_included" | "improperly_excluded" | "properly_excluded";

export interface SheetSectionDraft {
  key: string;
  title: string;
  count: number;
  /** Cents as an integer string sum is kept by code; amounts stay whole numbers here. */
  total: number;
}

export interface SurlRowDraft {
  key: string;
  sectionKey: "stratum_1" | "stratum_2";
  vendor: string;
  paidOn: string;
  amount: number;
  invoiceOn: string;
  servicePeriod: string;
  recordedIn: string;
  conclusion: { value: SurlConclusion; state: SheetCellState };
}

export interface SurlSheetDraft {
  procedure: string;
  sections: SheetSectionDraft[];
  /** The rows the handoff names field for field (SURL-01 to SURL-14, from SHT-01). */
  rows: SurlRowDraft[];
  /** Rows the backend scenario derives (SURL-15 to SURL-40): count and total only, never typed rows. */
  derived: { from: string; to: string; count: number; total: number }[];
  status: { rows: number; exceptions: number };
}
