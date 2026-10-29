// ENG-02 copy, verbatim from the handoff spec.md (docs/screens/ENG-02.md, Copy). Rail values, gate
// facts and work-item rows are data, never copy. The Record signed letter sheet is undesigned
// (P-07 R-9); its strings are recorded in the screen contract by P-07-T20.

export const COPY = {
  back: "‹ All Engagements",
  backHint: "Opens ENG-01 · all engagements",
  contracted: (d: string) => `Contracted ${d}`,
  tabs: {
    label: "Engagement sections",
    overview: "Overview",
    dashboard: "Dashboard",
    board: "Board",
    workItems: "Work items",
    team: "Team",
    letter: "Letter & terms",
    budget: "Budget",
    activity: "Activity", // P-07-T61: the tab's label (R2 tab list)
  },
  /** R2: the gear at the right end of the tabsbar; it opens ENG-11 (planned). */
  gear: "Engagement settings",
  /** The planned tabs' hosts in fixture builds (P-07-T28): their content is the target's. */
  planned: {
    dashboard: "Opens ENG-12 · the dashboard inside this record (see ENG-02f).",
    board: "Opens ENG-10 · the board inside this record (see ENG-02g).",
    budget: "Opens ENG-06 · budget, time and AI effort; Billing opens ENG-08.",
    team: "Opens ENG-05 · team and roles",
  },
  /** a: under the approver of record, for a non-attest client. */
  skeNotRequired: (client: string) =>
    `SKE designation not required — ${client} is not an attest client.`,
  roles: {
    engagement_partner: "Engagement partner",
    manager: "Manager",
    senior: "Senior",
    staff: "Staff",
    reviewer: "Reviewer",
    eqr_reviewer: "EQR reviewer",
    specialist: "Specialist",
    client_service: "Client service",
  } as Readonly<Record<string, string>>,
  rail: {
    title: "Summary",
    bands: {
      details: "Details",
      review_delivery: "Review and Delivery",
      client_portal: "Client Portal",
    },
  },
  keys: {
    client: "Client",
    entity: "Entity",
    service: "Service",
    type: "Type",
    standards: "Standards",
    methodology: "Methodology",
    period: "Period",
    office: "Office",
    close_plan: "Close plan",
    letter: "Letter",
    fee: "Fee",
    due_date: "Due date",
    partner: "Partner (reviewer)",
    preparer: "Preparer",
    client_service: "Client service",
    contact: "Contact",
    approver_of_record: "Approver of record",
    portal: "Portal",
    connections: "Connections",
    reminder: "Reminder",
  } as Readonly<Record<string, string>>,
  clientHint: "Opens CLI-02 · client record",
  letterHint: "Opens ENG-04 · engagement letter",
  archiveLocked: (d: string) => `Archive locked ${d} · WORM`,
  postLock: (n: string) => `Post-lock additions: ${n}`,
  canvas: {
    title: "Overview",
    activity: "Activity ›",
  },
  group: {
    gates: "Gates",
    workItems: "Work items",
    /** a: the close engagement's group ("7 of 12" is data). */
    monthly: "Monthly closes",
    team: "Team",
  },
  banner: {
    g3: (person: string, d: string) =>
      `Work items open when the letter is signed (G3). Letter viewed by ${person} · ${d}.`,
    g3NoView: "Work items open when the letter is signed (G3).",
    g3Action: "Open letter",
    prospect: (partner: string) => `Acceptance pending — ${partner}`,
    prospectAction: "Open acceptance ›",
    prospectHint: "Opens CLI-07 · acceptance and continuance",
  },
  empty: {
    workItems: "No work items yet.",
  },
  workItemHint: "Opens AUD-02 · audit cockpit",
  /** The status pill's ⌄ menu (spec.md: "Active / On hold… (On hold asks for a reason)"). The
   * dialog, the reason words and the toasts are undesigned; recorded in DEC-344. */
  status: {
    menu: "Status",
    active: "Active",
    onHold: "On hold…",
    dialogTitle: "Put on hold",
    dialogDescription:
      "Choose why the engagement is on hold. Set it back to Active from the status menu.",
    reason: "Reason",
    confirm: "Put on hold",
    held: "Engagement on hold",
    resumed: "Engagement active",
    reasons: {
      client_unresponsive: "Client unresponsive",
      fees_outstanding: "Fees outstanding",
      scope_change: "Scope change",
      independence_review: "Independence review",
      other: "Other",
    },
    errors: {
      illegal_transition: "Only an active engagement can go on hold.",
      failed: "Couldn’t change the status.",
    },
  },
  letter: {
    title: "Letter & terms",
    status: "Status",
    signedOn: "Signed",
    record: "Record signed letter…",
    sheetTitle: "Record signed letter",
    sheetDescription:
      "Record the letter both parties signed. The dates must fall after the acceptance decision.",
    clientSignedOn: "Client signed on",
    clientSigner: "Client signer",
    firmSignedOn: "Firm signed on",
    firmSigner: "Firm signer",
    datePlaceholder: "YYYY-MM-DD",
    choose: "Choose",
    save: "Record letter",
    saved: "Letter recorded",
    errors: {
      letter_before_acceptance: "The signature dates must fall after the acceptance decision.",
      gate_unmet: "The acceptance decision (G1) is not recorded yet.",
      engagement_archived: "This engagement is archived.",
      date: "Enter a date as YYYY-MM-DD.",
      failed: "Couldn’t record the letter.",
    },
  },
} as const;
