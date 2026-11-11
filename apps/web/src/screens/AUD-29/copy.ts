// AUD-29 copy and the Northwind PY2025 activity the artboards draw (P-05-T14; handoff AUD-29
// spec, verbatim): 23 events since Aug 19 at Mon Sep 14, 2026, 2:30 PM, newest first. Counts are
// the server's (All 23 · Human 12 · via Agent 11 · Policy 0); the screen shows them, never sums.

export type Frame = "a" | "b" | "c" | "d" | "e" | "f";
export const FRAMES: readonly Frame[] = ["a", "b", "c", "d", "e", "f"];
export type Segment = "all" | "human" | "agent" | "policy";
/** Where a row opens (P-05 AC-35): a built screen or a registered planned link. */
export type Target =
  "WB-09" | "AUD-06" | "AUD-07" | "AUD-03" | "AUD-08" | "ENG-02" | "CLI-07" | "SHL-17";
export const TARGETS: readonly Target[] = [
  "WB-09",
  "AUD-06",
  "AUD-07",
  "AUD-03",
  "AUD-08",
  "ENG-02",
  "CLI-07",
  "SHL-17",
];

export interface ActivityEvent {
  date: string;
  time: string;
  title: string;
  detail: string;
  agent: boolean;
  mark: "check" | "atom" | "glyph";
  target: Target;
}

export const EVENTS: readonly ActivityEvent[] = [
  {
    date: "Sep 14",
    time: "2:05 PM",
    title: "Cells signed off by Hannah Leclerc · Trial Balance",
    detail:
      "Reviewer (L2) · 7 lines (6 funds + total mutual funds & CITs) · 4 lines awaiting review",
    agent: false,
    mark: "check",
    target: "AUD-06",
  },
  {
    date: "Sep 14",
    time: "1:30 PM",
    title: "Run idle · Marcus Delaney via Agent",
    detail:
      "3 of 14 workpapers complete · 1 blocked on a partner decision · 2 waiting on inputs · Sampling held",
    agent: true,
    mark: "atom",
    target: "WB-09",
  },
  {
    date: "Sep 14",
    time: "1:15 PM",
    title: "Document accepted by Ana Cruz",
    detail:
      "Certified trust report (full year, signed) · Harborline Trust Company · 12 of 24 received",
    agent: false,
    mark: "check",
    target: "AUD-03",
  },
  {
    date: "Sep 14",
    time: "12:40 PM",
    title: "SOC 1 evaluation drafted · Marcus Delaney via Agent",
    detail:
      "Coverage gap Oct 1 – Dec 31, 2025 · waiting on the bridge letter · CUEC evidence 2 of 6",
    agent: true,
    mark: "atom",
    target: "WB-09",
  },
  {
    date: "Sep 14",
    time: "12:31 PM",
    title: "Risk Assessment revised to Version 2 · Marcus Delaney via Agent",
    detail:
      "R3 rationale cites Internal Control row 2 · decision routed to Margaret Okonkwo (1 significant risk, 1 rebuttal)",
    agent: true,
    mark: "atom",
    target: "AUD-08",
  },
  {
    date: "Sep 14",
    time: "12:20 PM",
    title: "Internal Control complete · Marcus Delaney via Agent",
    detail: "7 exceptions · severities proposed, not concluded",
    agent: true,
    mark: "atom",
    target: "WB-09",
  },
  {
    date: "Sep 14",
    time: "11:20 AM",
    title: "Run resumed · Marcus Delaney via Agent",
    detail: "Re-planned after the materiality decision",
    agent: true,
    mark: "atom",
    target: "WB-09",
  },
  {
    date: "Sep 14",
    time: "11:12 AM",
    title: "Materiality decided by Margaret Okonkwo",
    detail:
      "Version 2 · 1.5% of unadjusted net assets 16,812,400 = $252,200 · PM $189,150 · CT $12,610 · G4 1 of 2",
    agent: false,
    mark: "check",
    target: "AUD-07",
  },
  {
    date: "Sep 14",
    time: "10:40 AM",
    title: "General Audit Planning drafted · Marcus Delaney via Agent",
    detail: "Waiting on inputs: trust agreement, IRS opinion letter",
    agent: true,
    mark: "atom",
    target: "WB-09",
  },
  {
    date: "Sep 14",
    time: "10:15 AM",
    title: "Risk Assessment drafted · Marcus Delaney via Agent",
    detail: "Version 1 · 2 significant risks (management override mandatory, 1 proposed)",
    agent: true,
    mark: "atom",
    target: "AUD-08",
  },
  {
    date: "Sep 14",
    time: "10:02 AM",
    title: "Trial Balance prepared by Marcus Delaney",
    detail: "Adopted Agent run #4127 · Preparer (L1)",
    agent: false,
    mark: "check",
    target: "AUD-06",
  },
  {
    date: "Sep 14",
    time: "9:27 AM",
    title: "Materiality proposed · Marcus Delaney via Agent",
    detail: "Version 1 · blocked on a partner decision · routed to Margaret Okonkwo",
    agent: true,
    mark: "atom",
    target: "AUD-07",
  },
  {
    date: "Sep 14",
    time: "9:26 AM",
    title: "Trial Balance complete · Marcus Delaney via Agent",
    detail: "Agreed to Harborline net trust assets $16,812,400.00",
    agent: true,
    mark: "atom",
    target: "WB-09",
  },
  {
    date: "Sep 14",
    time: "9:24 AM",
    title: "Run started by Marcus Delaney",
    detail: "'yes, run it' · 14 workpapers across 5 levels · Auto mode off",
    agent: false,
    mark: "glyph",
    target: "WB-09",
  },
  {
    date: "Sep 11",
    time: "4:18 PM",
    title: "Document uploaded by Harborline Trust Company",
    detail: "Certified trust report (full year, signed) · third-party request",
    agent: false,
    mark: "glyph",
    target: "AUD-03",
  },
  {
    date: "Sep 10",
    time: "11:02 AM",
    title: "Fraud brainstorming minutes drafted · Marcus Delaney via Agent",
    detail: "From the Teams transcript · awaiting EP approval",
    agent: true,
    mark: "atom",
    target: "WB-09",
  },
  {
    date: "Sep 10",
    time: "10:45 AM",
    title: "Fraud brainstorming held by Margaret Okonkwo",
    detail: "4 attendees",
    agent: false,
    mark: "check",
    target: "ENG-02",
  },
  {
    date: "Sep 8",
    time: "2:05 PM",
    title: "Document uploaded by Sam Ortiz, Keystone",
    detail: "SOC 1 Type 2 — Keystone Retirement Services",
    agent: false,
    mark: "glyph",
    target: "AUD-03",
  },
  {
    date: "Sep 1",
    time: "9:00 AM",
    title: "PBC list published by Hannah Leclerc",
    detail: "24 requests · Dana Kowalski and 4 third parties",
    agent: false,
    mark: "check",
    target: "AUD-03",
  },
  {
    date: "Aug 31",
    time: "3:40 PM",
    title: "PBC list drafted · Marcus Delaney via Agent",
    detail: "PBC List Builder · BH Audit Methodology · EBP v3 template",
    agent: true,
    mark: "atom",
    target: "WB-09",
  },
  {
    date: "Aug 28",
    time: "11:15 AM",
    title: "Engagement letter signed by Dana Kowalski",
    detail:
      "§103(a)(3)(C) election acknowledged · countersigned by Margaret Okonkwo · G3 Contracted",
    agent: false,
    mark: "check",
    target: "ENG-02",
  },
  {
    date: "Aug 21",
    time: "4:00 PM",
    title: "Independence confirmed",
    detail: "5 of 5 team members · G2 Independent",
    agent: false,
    mark: "check",
    target: "ENG-02",
  },
  {
    date: "Aug 19",
    time: "10:30 AM",
    title: "Continuance approved by Margaret Okonkwo",
    detail: "G1 Accept",
    agent: false,
    mark: "check",
    target: "ENG-02",
  },
];

/** The server's counts (the segmented control). */
export const COUNTS: Record<Segment, number> = { all: 23, human: 12, agent: 11, policy: 0 };

export const COPY = {
  title: "Activity",
  search: "Search activity",
  events: (n: number) => `${String(n)} event${n === 1 ? "" : "s"}`,
  segments: { all: "All", human: "Human", agent: "via Agent", policy: "Policy" } as const,
  type: "Type",
  typeAll: "All",
  date: "Date",
  since: "Since Aug 19",
  download: "Download",
  open: "Open",
  policyEmptyTitle: "No policy acceptances.",
  policyEmptyBody: "Policy acceptance is off for Brightwater Hale (Firm settings › AI policy).",
  noMatch: "No events match this search.",
  separators: ["TODAY", "SEP 11", "SEP 10", "SEP 8", "SEP 1", "AUGUST"] as const,
  railRow: "Activity",
} as const;

/** The day separator a row sits under. */
export function separatorOf(date: string): string {
  if (date === "Sep 14") return "TODAY";
  if (date.startsWith("Aug")) return "AUGUST";
  return date.toUpperCase();
}
