// F-08-T15 (TASK-8847): TPL-23 "Insights — Client responsiveness" seed slice, Thu Oct 1, 2026 9:30 AM
// CT, season to date Jan 1 – Sep 30, 2026 (handoff TPL-23 spec). Every figure is the spec's;
// insights-responsiveness.foot.test.ts re-adds them (ADR-050): 2,804 + 1,432 + 214 = 4,450 due;
// 78 + 46 + 44 + 34 + 12 = 214 past due; Granite Peak 31 + 31 + 3 = 65.

export interface Tile {
  label: string;
  value: string;
  basis: string;
  delta?: { direction: "up" | "down"; words: string; improvement?: boolean };
}

export const FIRM_TILES: readonly Tile[] = [
  {
    label: "On-time rate",
    value: "63%",
    basis: "vs last season (58%)",
    delta: { direction: "up", words: "5 pts vs last season (58%)", improvement: true },
  },
  { label: "Past due now", value: "214", basis: "of 576 open requests" },
  {
    label: "Median days to first response",
    value: "3.1",
    basis: "vs last season (3.6)",
    delta: { direction: "down", words: "0.5 days vs last season (3.6)", improvement: true },
  },
  {
    label: "Median days to complete",
    value: "9.0",
    basis: "vs last season (10.4)",
    delta: { direction: "down", words: "1.4 days vs last season (10.4)", improvement: true },
  },
  { label: "Requests sent", value: "4,812", basis: "4,236 completed · 88.0%" },
  {
    label: "Median response · firm / client",
    value: "1.2 / 4.6",
    basis: "days from a message to the reply",
  },
];

export const GRANITE_TILES: readonly Tile[] = [
  { label: "On-time rate", value: "48%", basis: "31 of 65 · firm 63%" },
  { label: "Past due now", value: "3", basis: "of 3 open requests" },
  { label: "Median days to first response", value: "4.0", basis: "vs firm 3.1" },
  { label: "Median days to complete", value: "11.5", basis: "vs firm 9.0" },
  { label: "Requests sent", value: "65", basis: "62 completed · 95.4%" },
  {
    label: "Median response · firm / client",
    value: "1.2 / 4.6",
    basis: "days from a message to the reply",
  },
];

export const DUE = {
  firm: { onTime: 2804, late: 1432, pastDue: 214, due: 4450, centre: "63%" },
  granite: { onTime: 31, late: 31, pastDue: 3, due: 65, centre: "48%" },
};

export const QUARTERS = {
  categories: ["Q1", "Q2", "Q3"],
  y2026: [63.4, 64.0, 61.0],
  y2025: [55.0, 58.0, 61.0],
};

export const RESPONSE = [
  { key: "firm", label: "Firm", min: 0.2, q1: 0.6, median: 1.2, q3: 2.4, max: 5.5 },
  { key: "client", label: "Client", min: 0.8, q1: 2.6, median: 4.6, q3: 7.2, max: 10 },
];

export const AGES = [
  { key: "1-7", label: "1–7 days", value: 78 },
  { key: "8-14", label: "8–14 days", value: 46 },
  { key: "15-30", label: "15–30 days", value: 44 },
  { key: "31-60", label: "31–60 days", value: 34 },
  { key: "60+", label: "Over 60 days", value: 12 },
];

export interface LowRow {
  client: string;
  line: string;
  requests: number;
  pastDue: number;
  onTimePct: number;
  firstResponse: string;
  lastActivity: string;
  silent?: string;
}

export const LOWEST: readonly LowRow[] = [
  {
    client: "Fenwick Family Foundation",
    line: "Tax · Audit & assurance",
    requests: 9,
    pastDue: 6,
    onTimePct: 22,
    firstResponse: "11.5",
    lastActivity: "Aug 11",
    silent: "silent 51 days",
  },
  {
    client: "Estate of Walter Thornbury",
    line: "Tax",
    requests: 13,
    pastDue: 3,
    onTimePct: 31,
    firstResponse: "7.0",
    lastActivity: "Sep 29",
  },
  {
    client: "Gloria Mendez",
    line: "Tax",
    requests: 11,
    pastDue: 7,
    onTimePct: 36,
    firstResponse: "6.5",
    lastActivity: "Sep 18",
  },
  {
    client: "Granite Peak Outdoor Supply, Inc.",
    line: "Audit & assurance",
    requests: 65,
    pastDue: 3,
    onTimePct: 48,
    firstResponse: "4.0",
    lastActivity: "Sep 30",
  },
  {
    client: "Northwind Robotics",
    line: "Audit & assurance",
    requests: 28,
    pastDue: 2,
    onTimePct: 57,
    firstResponse: "3.5",
    lastActivity: "Sep 30",
  },
];

export const GRANITE_PAST_DUE = [
  {
    request: "Inventory roll-forward and explanation of the 24.4% increase, 6/30/2026",
    owner: "Luis Ferrante",
    due: "Sep 18",
    late: 13,
  },
  {
    request: "Front Range Bank covenant compliance certificate, FY2026",
    owner: "Luis Ferrante",
    due: "Sep 21",
    late: 10,
  },
  {
    request: "Board of directors minutes, Jan 1 – Aug 31, 2026",
    owner: "No owner",
    due: "Sep 25",
    late: 6,
  },
];

export const GRANITE = "Granite Peak Outdoor Supply, Inc.";
