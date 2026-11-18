// F-08-T03 (DEC-5618): draft view-model types for the T22 add-in pane and the TPL-24 specimen
// (F-08 §5 "View models"), until W-04's add-in contract lands and deletes this file.
export interface LeadsheetRowDraft {
  row: number;
  account: string | null;
  label: string;
  prior: number;
  current: number;
  ref: string;
}

export interface AddinDraft {
  workbook: string;
  rows: LeadsheetRowDraft[];
  totalRow: number;
  links: { cell: string; evidence: string; page: number }[];
  tickmarks: { mark: string; count: number }[];
  wordIncoming: { label: string; old: string; new: string }[];
}
