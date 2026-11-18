// F-08-T03 (DEC-5618): draft view-model types for the T21 analytics kit and the TPL-23 specimen
// (F-08 §5 "View models"), until I-03's insights contract lands and deletes this file.
export interface ResponsivenessClientDraft {
  client: string;
  serviceLine: string;
  requests: number;
  pastDue: number;
  onTimePct: number;
  firstResponseDays: number;
  lastActivity: string;
}

export interface ResponsivenessDraft {
  asOf: string;
  due: { onTime: number; late: number; pastDue: number };
  openNotDue: number;
  pastDueByAge: { label: string; count: number }[];
  quarters: { label: string; due: number; onTime: number }[];
  lowest: ResponsivenessClientDraft[];
}
