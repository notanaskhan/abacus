// ENG-01 copy, verbatim from the handoff spec.md (docs/screens/ENG-01.md, Copy). Row text
// (engagement names, clients, periods, sub-lines, letter dates, next-due labels) is data, never
// copy. Status words come from the registry (`engagement`), never from here.

import type { EngagementLine } from "../../domain/engagements";

export const COPY = {
  title: "Engagements",
  noun: "engagements",
  search: "Search engagements",
  segmentsLabel: "Service line",
  segments: {
    all: "All",
    tax: "Tax",
    audit: "Audit",
    cas: "CAS",
    advisory: "Advisory",
  } satisfies Record<EngagementLine | "all", string>,
  chips: {
    office: "Office",
    allOffices: "All offices",
    partner: "Partner",
    all: "All",
    letter: "Letter",
    any: "Any",
    notSigned: "Not signed",
    signed: "Signed",
    nextDue: "Next due",
    pastDue: "Past due",
    within7: "Within 7 days",
    within30: "Within 30 days",
    period: "Period",
    current: "Current",
    prior: "Prior",
    allPeriods: "All",
  },
  /** "275 engagements · 1 prospect · 4 awaiting a signed letter · 2 past due" */
  summary: (total: string, prospect: string, awaiting: string, pastDue: string) =>
    `${total} engagements · ${prospect} prospect · ${awaiting} awaiting a signed letter · ${pastDue} past due`,
  /** "Showing 17 of 275" */
  showing: (n: string, total: string) => `Showing ${n} of ${total}`,
  /** "+ New engagement": the plus is the button's icon. */
  newEngagement: "New engagement",
  newEngagementHint: "Opens ENG-03 · new engagement wizard",
  loadMore: "Load more",
  columns: {
    engagement: "Engagement",
    client: "Client",
    type: "Type",
    period: "Period",
    office: "Office",
    partner: "Partner",
    status: "Status",
    workItems: "Work items",
    letter: "Letter",
    nextDue: "Next due",
  },
  /** The Type cell: "{line} · {type}" ("CAS · Monthly close", "Tax · 1065"). */
  lines: { tax: "Tax", audit: "Audit", cas: "CAS", advisory: "Advisory" } satisfies Record<
    EngagementLine,
    string
  >,
  types: {
    fs_audit: "FS audit",
    ebp_audit: "EBP DC",
    review: "Review (AR-C 90)",
    compilation: "Compilation",
    preparation: "Preparation",
    agreed_upon_procedures: "Agreed-upon procedures",
    soc1: "SOC 1",
    soc2: "SOC 2",
    readiness: "Readiness",
    internal_audit: "Internal audit",
    tax_compliance: "Return",
    cas_monthly_close: "Monthly close",
    notice_response: "Notice",
    advisory: "Project",
  },
  /** "12 closes", "1 return" (the work items' own nouns). */
  workItems: {
    close: ["close", "closes"],
    tax_return: ["return", "returns"],
    notice: ["notice", "notices"],
    advisory_project: ["project", "projects"],
    audit: ["audit", "audits"],
    review: ["review", "reviews"],
    engagement: ["engagement", "engagements"],
    /** Accepted, the letter not signed: no work item opens yet (Bluestem). */
    waitingLetter: "Opens when the letter is signed",
    /** A Prospect: nothing opens before G1 and G3 (the Thornbury estate). */
    prospect: "open after acceptance (G1) and a signed letter (G3)",
  },
  letter: {
    signed: (on: string) => `✓ Signed ${on}`,
    sent: (on: string, signed: number, signers: number) =>
      `Sent ${on} · ${String(signed)} of ${String(signers)}`,
    viewed: (on: string, signed: number, signers: number) =>
      `Viewed ${on} · ${String(signed)} of ${String(signers)}`,
    partial: (signed: number, signers: number) => `${String(signed)} of ${String(signers)} signed`,
    none: "—",
  },
  due: {
    pastDue: (n: number) => `${String(n)} days past due`,
    days: (n: number) => (n === 1 ? "1 day" : `${String(n)} days`),
  },
  /** b: above the table. */
  bannerG3: "Portal requests and billing stay held until the letter is signed (G3).",
  /** d: "No engagements match 'Harbor Lane'." */
  noMatch: (q: string) => `No engagements match '${q}'.`,
  clear: "Clear filters",
  /** A firm with no engagement at all (no artboard; the T1c frame's words). */
  empty: { title: "No engagements yet." },
  rowHint: (name: string) => `Opens ENG-02 · ${name}`,
} as const;
