// ADM-03 copy, verbatim from the handoff (screens/ADM-03 spec.md, revision.md R2 and screenshots)
// and docs/screens/ADM-03.md, whose deviations it carries: the walls helper without its count
// sentence (DEC-43, DF-14), the wall toast and "Awaiting …" (DEC-73, INV-5), the walls step-up
// (R-5), the offshore banner and group helper after TASK-1207 (DEC-352). Names, offices, teams,
// clients and dates are data, never here.

const n = (value: number): string => String(value);

export type Line = "audit" | "tax" | "cas" | "advisory";
export type Reason =
  "personal_relationship" | "financial_interest" | "relative" | "prior_employment" | "other";

export const COPY = {
  title: "Firm settings",
  navTitle: "Settings",
  back: "Back",
  section: "Offices & teams",
  notAllowed: "You don't have access to firm settings.",
  readOnly: "Only firm admins can edit these settings.",
  unsaved: "Unsaved changes",
  saved: "Firm settings saved",
  stale: "These settings changed since you opened them. Reload to see them.",
  error: "Couldn't load this section. Try again.",
  stepUpTitle: "Confirm it's you to save firm settings",
  stepUpBody: "Sign in again to confirm it's you, then save.",
  signInAgain: "Sign in again",
  cancel: "Cancel",
  fieldsets: {
    offices: "Offices",
    teams: "Teams & groups",
    lines: "Service lines",
    walls: "Ethical walls",
    offshore: "Offshore & restricted access (§7216)",
  },
  adds: {
    office: "Office",
    group: "Group",
    line: "Service line",
    wall: "Wall",
  },
  officeName: (name: string, hq: boolean) => (hq ? `${name} · HQ` : name),
  officeSeats: (seats: number) => `${n(seats)} seats`,
  officeReturns: (returns: number, hq: boolean) =>
    hq ? `· ${n(returns)} TY2025 returns` : `· ${n(returns)} returns`,
  officeToggle: (name: string) => `Show or hide ${name}`,
  openSeats: (name: string) => `Open People filtered to ${name}`,
  rows: {
    address: "Address",
    timeZone: "Time zone",
    lead: "Office lead",
    code: "Office code",
    pool: "Default reviewer pool",
  },
  codeHelp: "Used in CCH Axcess office mapping (ADM-08).",
  allOffices: "All offices",
  allOfficesValue: (seats: number, returns: number | undefined) =>
    `${n(seats)} seats${returns === undefined ? "" : ` · ${n(returns)} returns`}`,
  timeZones: [
    { value: "America/New_York", label: "Eastern Time (ET)" },
    { value: "America/Chicago", label: "Central Time (CT)" },
    { value: "America/Denver", label: "Mountain Time (MT)" },
    { value: "America/Los_Angeles", label: "Pacific Time (PT)" },
  ],
  teamNames: {
    "Client accounting": "Client accounting (CAS)",
  } as Readonly<Record<string, string>>,
  teamsSum: (counts: readonly number[]) =>
    `${counts.map(n).join(" + ")} = ${n(counts.reduce((a, b) => a + b, 0))} seats`,
  groups: "Groups",
  groupHelp: {
    eqr_pool: "Eligible EQR reviewers; cannot be EQR on their own engagements (SQMS No. 2).",
    monitoring_reviewers: "Objective inspectors for ADM-12.",
  } as Readonly<Record<string, string>>,
  accessEnds: "Access ends",
  more: (count: number) => `+${n(count)}`,
  members: (name: string) => `${name} members`,
  lines: {
    columns: ["Service line", "Lead", "Content visible to", "Cross-line access"],
    names: {
      audit: "Audit & assurance (incl. SOC & IT, internal audit)",
      tax: "Tax",
      cas: "Client accounting (CAS)",
      advisory: "Advisory",
    } as Readonly<Record<Line, string>>,
    visibility: [
      { value: "engagement_team_only", label: "Engagement team only" },
      { value: "service_line", label: "Service line" },
    ],
    crossLine: {
      handoffs_only: "Hand-offs only",
      by_request: "By request (partner approves)",
    } as Readonly<Record<string, string>>,
    auditCrossLine: "Hand-offs only (AUD-38)",
    example:
      "Granite Peak Outdoor Supply, Inc. — FY2026 audit (MO · HL · SB · CH) and FY2026 Form 1120 (LW · IM · VH): the tax team sees the final TB the audit hands off, never the audit file.",
    helper:
      "Separation sits on top of ethical walls and need to know: a person on both teams sees both. Admins see engagement metadata and counts, never content (Insights).",
    narrowed: {
      tax: "Tax staff lose access to tax engagements they are not staffed on. Save to apply.",
      cas: "CAS staff lose access to CAS engagements they are not staffed on. Save to apply.",
      advisory:
        "Advisory staff lose access to advisory engagements they are not staffed on. Save to apply.",
      audit: "",
    } as Readonly<Record<Line, string>>,
    locked: "Audit content is visible to the engagement team only.",
  },
  walls: {
    columns: ["Person", "Walled from", "Reason", "Added", "Approved by"],
    helper: "Walled people cannot open, search, be assigned to, or run agents on these clients.",
    stepUp: "Confirm it's you to view walls",
    stepUpAction: "Confirm it's you",
    awaiting: (partner: string) => `Awaiting ${partner}`,
    added: (when: string, by: string) => `${when} by ${by}`,
    today: (time: string) => `Today ${time}`,
    approve: "Approve",
    lift: "Lift",
    approveFor: (person: string) => `Approve the wall on ${person}`,
    liftFor: (person: string) => `Lift the wall on ${person}`,
    open: (person: string, client: string) => `Open the wall on ${person} from ${client}`,
    approved: "Wall approved",
    lifted: "Wall lifted",
    liftReason: "Lifted from Offices & teams",
    empty: "No ethical walls.",
  },
  reasons: {
    personal_relationship: "Personal relationship",
    financial_interest: "Financial interest",
    relative: "Relative",
    prior_employment: "Prior employment",
    other: "Other",
  } as Readonly<Record<Reason, string>>,
  sheet: {
    title: "New ethical wall",
    person: "Person",
    client: "Walled from",
    reason: "Reason",
    reasonText: "Details",
    reasonPlaceholder: "Why this person is walled",
    effect: "Effect",
    effects: (assignments: number) => [
      `Remove from ${n(assignments)} current assignments`,
      "Hide from search, Go… and Inbox",
      "Block agent runs she starts on this client",
      "Exclude from portal threads",
    ],
    approval: "Approval",
    requires: "Requires a partner",
    choose: "Choose",
    save: "Save",
    conflict: (person: string) =>
      `${person} leads this relationship. Reassign the relationship partner first.`,
    exists: (person: string, client: string) => `${person} is already walled from ${client}.`,
    own: "You can't wall yourself.",
    toast: (partner: string) => `Wall added · approval requested from ${partner}`,
    toastNoApprover: "Wall added",
  },
  log: {
    title: "Ethical wall",
    wall: "Wall",
    details: "Details",
    added: "Added",
    approvedBy: "Approved by",
    log: "Log",
    label: "Wall log",
    events: {
      "wall.created": (person: string) => `Ethical wall added by ${person}`,
      "wall.approved": (person: string) => `Approved by ${person}`,
      "wall.removed": (person: string) => `Wall lifted by ${person}`,
    } as Readonly<Record<string, (person: string) => string>>,
    someone: "Someone",
  },
  offshore: {
    group: "Offshore / restricted group",
    members: (count: number) => `${n(count)} ${count === 1 ? "member" : "members"}`,
    groupHelp:
      "Members can be assigned only to clients with a valid §7216 consent to disclosure to offshore preparers; SSNs stay masked (Treas. Reg. §301.7216-3(b)(4); Rev. Proc. 2013-14 §5.07).",
    consented: "Clients with a valid offshore consent",
    registry: "Consent registry ›",
    block: "Block offshore assignment without consent",
    blockHelp: "Required by firm policy; cannot be turned off.",
    mask: "Mask TINs for restricted members",
    banner: (person: string) =>
      `${person} can't be assigned to a client until its offshore consent is signed. SSNs stay masked.`,
  },
} as const;
