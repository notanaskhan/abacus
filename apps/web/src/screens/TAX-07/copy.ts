// TAX-07 copy and the Feld activity the artboards draw (T-04-T27; handoff TAX-07 spec, verbatim).
// 24 events at Mon Sep 14, 9:24 AM, newest first; events sharing a timestamp keep their causal
// order (import 9:30 before its approval 9:31). Engine ids progress V1 (Feb 3) → V2 (Apr 14) → V3
// (Sep 10). Every approval names a person; "Accrued Agent" only proposes and self-checks.

export type Frame = "a" | "b" | "b2" | "c" | "d" | "e" | "e2" | "f";
export const FRAMES: readonly Frame[] = ["a", "b", "b2", "c", "d", "e", "e2", "f"];

export type Kind = "approval" | "client" | "agent" | "engine" | "issue";
export type Marker =
  | "check"
  | "reverse"
  | "mail"
  | "upload"
  | "download"
  | "send"
  | "file"
  | "plus"
  | "help"
  | "atom";
export interface Event {
  date: string;
  time: string;
  marker: Marker;
  title: string;
  sub?: string;
  kind: Kind;
  link?: "SHL-08" | "INB-01" | "TXP-12" | "TAX-09" | "SIG-01" | "TAX-12";
}

export const EVENTS: readonly Event[] = [
  {
    date: "Sep 14",
    time: "9:12 AM",
    marker: "mail",
    title: "Email received from Claire Feld",
    sub: "2 attachments waiting in Inbox · Form 1095-C (2025, 2024)",
    kind: "client",
    link: "INB-01",
  },
  {
    date: "Sep 11",
    time: "4:05 PM",
    marker: "check",
    title: "Documents approved by Samuel Ito",
    sub: "4 documents · Manager review",
    kind: "approval",
  },
  {
    date: "Sep 10",
    time: "9:31 AM",
    marker: "check",
    title: "Return import approved by Samuel Ito",
    sub: "Imported from tax engine",
    kind: "approval",
  },
  {
    date: "Sep 10",
    time: "9:30 AM",
    marker: "download",
    title: "Return imported from tax engine by Samuel Ito",
    sub: "2025I:FeldJ:V3",
    kind: "engine",
    link: "TAX-09",
  },
  {
    date: "Sep 9",
    time: "5:12 PM",
    marker: "check",
    title: "Detail review signed off by Olivia Brandt",
    sub: "L1 · 1040 Review Checklist v6 · 2 review notes cleared",
    kind: "approval",
  },
  {
    date: "Sep 9",
    time: "11:40 AM",
    marker: "help",
    title: "Question answered by Claire Feld",
    sub: "Residency facts · 3 attachments",
    kind: "client",
  },
  {
    date: "Sep 8",
    time: "6:02 PM",
    marker: "check",
    title: "Submitted for review by Kevin Osei",
    sub: "38 of 38 documents approved (preparer)",
    kind: "approval",
  },
  {
    date: "Aug 28",
    time: "9:05 AM",
    marker: "check",
    title: "Issue resolved by Kevin Osei",
    sub: "Refund bank account received — direct deposit authorization",
    kind: "issue",
  },
  {
    date: "Aug 27",
    time: "2:15 PM",
    marker: "check",
    title: "Issue resolved by Kevin Osei",
    sub: "1099-G NY refund of 2024 tax — not taxable (2024 SALT limited to $10,000)",
    kind: "issue",
  },
  {
    date: "Aug 27",
    time: "10:20 AM",
    marker: "check",
    title: "Issue resolved by Kevin Osei",
    sub: "Confirm digital asset transactions — Claire Feld answered No",
    kind: "issue",
  },
  {
    date: "Aug 26",
    time: "9:48 AM",
    marker: "check",
    title: "Initial draft approved by Kevin Osei",
    sub: "Checkpoint 'Initial draft'",
    kind: "approval",
  },
  {
    date: "Aug 25",
    time: "11:04 PM",
    marker: "atom",
    title: "Initial draft self-checked by Accrued Agent",
    sub: "7 issues raised",
    kind: "agent",
  },
  {
    date: "Aug 25",
    time: "11:02 PM",
    marker: "file",
    title: "Initial draft prepared by Accrued Agent",
    sub: "Return Drafter · 36 documents · pro forma 2025I:FeldJ:V2",
    kind: "agent",
  },
  {
    date: "Aug 24",
    time: "3:48 PM",
    marker: "send",
    title: "Draft K-1 shared by Olivia Brandt",
    sub: "Ridgeline Property Partners, LP · Draft K-1 · pre-release",
    kind: "client",
    link: "TXP-12",
  },
  {
    date: "Aug 7",
    time: "6:22 PM",
    marker: "upload",
    title: "Documents uploaded by Claire Feld",
    sub: "Charitable receipts · 7 files",
    kind: "client",
    link: "SHL-08",
  },
  {
    date: "Aug 5",
    time: "8:10 PM",
    marker: "upload",
    title: "Document uploaded by Jonah Feld",
    sub: "Halvard Securities 2025 Consolidated 1099",
    kind: "client",
    link: "SHL-08",
  },
  {
    date: "Aug 3",
    time: "4:52 PM",
    marker: "check",
    title: "Email attachments filed by Kevin Osei",
    sub: "W-2 Mercer Hill Health · Form 1098 Hudson Mutual Savings",
    kind: "client",
  },
  {
    date: "Apr 14",
    time: "3:20 PM",
    marker: "check",
    title: "Extension accepted by IRS and NY DTF",
    sub: "Form 4868 (paid 10,000) · NY IT-370 (paid 6,000) · filed by Samuel Ito",
    kind: "engine",
  },
  {
    date: "Apr 14",
    time: "9:02 AM",
    marker: "download",
    title: "Return imported from tax engine by Samuel Ito",
    sub: "2025I:FeldJ:V2 · extension projection",
    kind: "engine",
    link: "TAX-09",
  },
  {
    date: "Feb 3",
    time: "10:41 AM",
    marker: "download",
    title: "Return imported from tax engine by Kevin Osei",
    sub: "2025I:FeldJ:V1 · pro forma",
    kind: "engine",
    link: "TAX-09",
  },
  {
    date: "Feb 3",
    time: "10:40 AM",
    marker: "send",
    title: "Binder published by Kevin Osei",
    sub: "2025 Binder · 7 requests",
    kind: "client",
  },
  {
    date: "Feb 3",
    time: "10:11 AM",
    marker: "plus",
    title: "Binder created by Kevin Osei",
    sub: "From the 2024 return",
    kind: "client",
  },
  {
    date: "Feb 2",
    time: "8:15 PM",
    marker: "check",
    title: "§7216 consents signed by Claire Feld and Jonah Feld",
    sub: "Use · AI disclosure (2 consents, each signed separately) · expires Dec 31, 2026",
    kind: "client",
    link: "SIG-01",
  },
  {
    date: "Jan 14",
    time: "9:02 AM",
    marker: "send",
    title: "Engagement letter and §7216 consents sent by Grace Holloway",
    kind: "client",
    link: "SIG-01",
  },
];

/** b: the assistant's box 18A fix, proposed at 9:29 AM. */
export const PROPOSED_EVENT: Event = {
  date: "Sep 14",
  time: "9:29 AM",
  marker: "atom",
  title: "Change proposed by Accrued Agent",
  sub: "Form 1040 line 2a 0 → 1,550 · IT-201 line 20 0 → 1,550",
  kind: "agent",
};

/** d: Sep 19, delivered, newest first (envelope and ack events). The handoff times only the two
 *  acceptances; the others' times come from the envelope and ack events in the seed. */
export const DELIVERED: readonly Event[] = [
  {
    date: "Sep 19",
    time: "8:55 AM",
    marker: "check",
    title: "NY return accepted",
    kind: "engine",
    link: "TAX-12",
  },
  {
    date: "Sep 18",
    time: "2:47 PM",
    marker: "check",
    title: "Federal return accepted",
    sub: "Submission ID ••••••2614 · Sep 18, 2:47 PM",
    kind: "engine",
    link: "TAX-12",
  },
  {
    date: "",
    time: "",
    marker: "send",
    title: "Return transmitted by Daniel Reyes",
    sub: "CCH Axcess e-file",
    kind: "engine",
  },
  {
    date: "",
    time: "",
    marker: "check",
    title: "Form 8879 signed by Jonah Feld",
    kind: "client",
    link: "SIG-01",
  },
  {
    date: "",
    time: "",
    marker: "check",
    title: "Form 8879 signed by Claire Feld",
    kind: "client",
    link: "SIG-01",
  },
  {
    date: "",
    time: "",
    marker: "send",
    title: "Envelope sent by Grace Holloway",
    kind: "client",
    link: "SIG-01",
  },
  {
    date: "",
    time: "",
    marker: "download",
    title: "Return exported to tax engine by Samuel Ito",
    sub: "2025I:FeldJ:V3",
    kind: "engine",
    link: "TAX-09",
  },
  {
    date: "",
    time: "",
    marker: "check",
    title: "Return approved by Daniel Reyes",
    sub: "Final review complete · BH-TAX-02",
    kind: "approval",
  },
  { date: "", time: "", marker: "check", title: "All review items cleared", kind: "approval" },
];

export interface Checkpoint {
  key: string;
  name: string;
  author: string;
  at: string;
  state: "current" | "approved" | "proposed";
  starred?: boolean;
  approvedBy?: string;
}

export const CHECKPOINTS: readonly Checkpoint[] = [
  {
    key: "manager",
    name: "Manager review",
    author: "Samuel Ito",
    at: "Sep 11, 4:05 PM",
    state: "current",
    starred: true,
  },
  {
    key: "engineV3",
    name: "Engine import V3",
    author: "Samuel Ito",
    at: "Sep 10, 9:31 AM",
    state: "approved",
  },
  {
    key: "residency",
    name: "Residency facts",
    author: "Accrued Agent",
    at: "Sep 9, 11:52 AM",
    state: "approved",
    approvedBy: "Kevin Osei",
  },
  {
    key: "submitted",
    name: "Submitted for review",
    author: "Kevin Osei",
    at: "Sep 8, 6:02 PM",
    state: "approved",
  },
  {
    key: "initial",
    name: "Initial draft",
    author: "Accrued Agent",
    at: "Aug 25, 11:02 PM",
    state: "approved",
  },
  {
    key: "v2",
    name: "Extension projection (V2)",
    author: "Samuel Ito",
    at: "Apr 14, 9:02 AM",
    state: "approved",
  },
  {
    key: "v1",
    name: "Pro forma (V1)",
    author: "Kevin Osei",
    at: "Feb 3, 10:41 AM",
    state: "approved",
  },
];

export const PROPOSED_CHECKPOINT: Checkpoint = {
  key: "box18a",
  name: "K-1 box 18A",
  author: "Accrued Agent",
  at: "9:29 AM",
  state: "proposed",
};

/** b2: SHL-16's steps for the proposed checkpoint (old → new, cause). */
export const PROPOSED_DIFF: readonly {
  field: string;
  old: string;
  next: string;
  cause: string;
}[] = [
  { field: "Form 1040 line 2a", old: "0", next: "1,550", cause: "Ridgeline K-1 box 18A" },
  {
    field: "IT-201 line 20",
    old: "0",
    next: "1,550",
    cause: "New York addition (no NY obligations)",
  },
];

export const FILTERS: readonly { key: Kind | "all"; label: string }[] = [
  { key: "all", label: "All events" },
  { key: "approval", label: "Approvals" },
  { key: "client", label: "Client" },
  { key: "agent", label: "Agent" },
  { key: "engine", label: "Tax engine" },
  { key: "issue", label: "Issues" },
];

export const COPY = {
  title: "2025 Form 1040",
  client: "Jonah & Claire Feld",
  state: "In review · Manager",
  tabs: ["Overview", "Intake 2", "Review 37", "Issues 4", "Activity"],
  tabsAfterFix: ["Overview", "Intake 2", "Review 37", "Issues 3", "Activity"],
  sync: "Synced Sep 10",
  chip: "☰ Checkpoints",
  chipProposed: "☰ 1 proposed",
  chipNone: "✓ No changes needed",
  search: "Search Activity",
  activity: "Activity",
  checkpoints: "Checkpoints",
  compare: "Compare…",
  review: "Review",
  restore: "Restore…",
  approve: "Approve",
  star: "Star",
  current: "Current",
  approved: "Approved",
  proposed: "Proposed",
  emptyFilter: "No events match this filter.",
  drawer: "Checkpoint changes",
} as const;
