// TXP-12 copy, verbatim from the handoff (screens/TXP-12 spec.md and README.md) with T-02's
// deviations: DV-9 (no agent drafts in the pilot: the K-3 tooltip and the empty state name the
// CCH Axcess import), DV-10 (the details-change tag and review sheet) and DEC-1575 (the masked TIN
// moves to the expanded row: no TIN on a list row, ADR-031).

const FORM: Readonly<Record<string, string>> = {
  "1065": "1065",
  "1120s": "1120-S",
  "1041": "1041",
};

export function formLabel(form: string): string {
  return FORM[form] ?? form;
}

/** The release check's failing codes, named (the acceptance: every failing check named). */
export const FAILING: Readonly<Record<string, string>> = {
  not_final_approved: "final approval",
  no_packages: "no K-1s imported",
  final_k1s_missing: "final K-1s not imported",
  nothing_to_release: "nothing left to release",
  no_release_policy: "no release signer in BH-TAX-02",
  recipient_contact_missing: "a recipient has no delivery contact",
};

export const COPY = {
  title: "K-1 package",
  back: (year: number, form: string) => `${String(year)} Form ${formLabel(form)}`,
  returnDue: (on: string) => `Return due ${on}`,
  returnFiled: "Return filed",
  releasedPill: (on: string) => `Released ${on}`,
  filters: {
    return: "Return",
    recipient: "Recipient",
    status: "Status",
    delivery: "Delivery",
  },
  all: "All",
  portal: "Portal",
  returnOption: (year: number, form: string, client: string) =>
    `${String(year)} Form ${formLabel(form)} · ${client.split(/[ ,]/)[0] ?? client}`,
  tiles: {
    not_prepared: "Not prepared",
    draft: "Draft K-1 · pre-release",
    released: "Released",
    viewed: "Viewed",
    downloaded: "Downloaded",
    bounced: "Bounced",
  },
  releaseBlocked: (reasons: string) => `Release blocked: ${reasons}`,
  finalApprovalBy: (signer: string) => `final approval (${signer}, BH-TAX-02)`,
  releasedSummary: (when: string, bounced: number) =>
    `Released ${when} to the portal (POR-13)${bounced > 0 ? ` · ${String(bounced)} invite${bounced === 1 ? "" : "s"} bounced` : ""}`,
  readySummary: "Ready to release: final approval recorded",
  search: "Search recipients",
  noun: "recipients",
  paneTitle: (n: number) => `Recipients · ${String(n)}`,
  shareDraft: "Share draft internally…",
  releaseK1s: "Release K-1s…",
  resend: "Resend…",
  requiresApproval: (signer: string) => `Requires final approval by ${signer}`,
  requires: (reasons: string) => `Requires ${reasons}`,
  draftsBanner: (n: number, names: string) =>
    `Drafts only. ${n === 1 ? "One draft is" : `${n === 2 ? "Two" : String(n)} drafts are`} shared internally with the ${names}, where they block final approval until release.`,
  draftsOnly: "Drafts only.",
  columns: {
    expand: "",
    recipient: "Recipient",
    type: "Type",
    period: "Period",
    k1: "K-1",
    k3: "K-3",
    states: "State K-1s",
    letter: "Letter",
    status: "Status",
    handoff: "Internal handoff",
    delivery: "Delivery",
  },
  kind: { gp: "GP", lp: "LP", shareholder: "S", beneficiary: "B" } as const,
  kindName: {
    gp: "General partner",
    lp: "Limited partner",
    shareholder: "Shareholder",
    beneficiary: "Beneficiary",
  } as const,
  fullYear: "Full year",
  k3Draft: "K-3 (draft)",
  k3: "K-3",
  k3NotRequired: "Not required",
  // DV-9: the K-3 note names the import, not an agent.
  k3Tip:
    "CCH Axcess produced Schedules K-2/K-3 because Pell Street Ventures LLC and Pell Street II LLC are partnerships (domestic filing exception unavailable).",
  k3Info: "Why every partner gets a Schedule K-3",
  handoffShared: (target: string, on: string) => `${target} · shared ${on}`,
  handoffReplaced: (target: string) => `${target} · final replaced draft`,
  handoffTarget: (name: string, form: string | null) =>
    form === null ? name : `${name.split(" ").at(-1) ?? name} ${formLabel(form)}`,
  bounced: "Invite email bounced — update address",
  detailsChange: (kind: string, on: string) =>
    `Details change · ${kind === "address" ? "Address" : kind.toUpperCase().replace("W", "W-")} uploaded ${on}`,
  reviewDetails: "Review details change…",
  expandRow: (name: string) => `Show ${name}'s K-1`,
  collapseRow: (name: string) => `Hide ${name}'s K-1`,
  expanded: {
    asDrafted: "(as drafted)",
    tin: "TIN",
    states: "State lines",
    attachments: "Attachments",
    noFigures: "Box figures show to readers of the return's content.",
  },
  documents: {
    k1: (draft: boolean) => (draft ? "K-1 (draft)" : "K-1"),
    k3: (draft: boolean) => (draft ? "Schedule K-3 (draft)" : "Schedule K-3"),
    letter: (draft: boolean) => (draft ? "Cover letter (draft)" : "Cover letter"),
    states: (n: number) => `State K-1s (${String(n)})`,
  },
  share: {
    title: "Share draft internally",
    body: "Draft K-1s go to related returns inside Accrued only. Nothing appears in the client portal until release.",
    target: (client: string, year: number, form: string) =>
      `${client} · ${String(year)} Form ${formLabel(form)}`,
    from: (recipient: string) => `K-1 from ${recipient}`,
    sharedOn: (on: string) => `Draft shared ${on}`,
    warning: "Drafts block final approval of the receiving return.",
    confirm: (n: number) => `Share ${String(n)} draft${n === 1 ? "" : "s"}`,
    none: "No related returns in the firm for these recipients.",
    done: (n: number) => `${String(n)} draft${n === 1 ? "" : "s"} shared`,
    partial: (n: number) =>
      `${String(n)} draft${n === 1 ? "" : "s"} shared; the rest were refused. Check the rows.`,
    failed: "The drafts weren't shared. Try again.",
  },
  release: {
    title: "Release K-1s",
    recipients: (n: number) => `${String(n)} recipient${n === 1 ? "" : "s"}`,
    portalTo: (contact: string | null) => `Portal · ${contact ?? "no contact"}`,
    contents: (k3: boolean, states: number) =>
      [
        "K-1",
        ...(k3 ? ["K-3"] : []),
        ...(states > 0 ? [`${String(states)} state K-1s`] : []),
        "letter",
      ].join(" · "),
    delivery: "Delivery",
    deliveryValue: "Portal · My K-1s (POR-13), with an invite email to each recipient",
    email: "Invite email",
    emailValue: "Deliverable ready",
    note: (targets: string) =>
      targets === ""
        ? "The release is logged to Activity (TAX-07)."
        : `The final K-1s replace the drafts shared with the ${targets}. The release is logged to Activity (TAX-07).`,
    confirm: "Release",
    releasing: (n: number) => `Releasing ${String(n)} K-1${n === 1 ? "" : "s"} to the portal`,
    undone: "Release undone. Nothing was sent.",
  },
  resendDialog: {
    title: "Resend K-1",
    body: (recipient: string) =>
      `Choose the contact who receives ${recipient}'s invite. The bounced address stays on record.`,
    recipient: "To",
    pick: "Choose a contact",
    confirm: "Resend",
    sent: (recipient: string) => `Invite resent for ${recipient}`,
  },
  details: {
    title: "Review details change",
    accept: "Accept",
    reject: "Reject",
    none: "No pending details change.",
    submitted: (kind: string, on: string) => `${kind} submitted ${on}`,
  },
  // DV-9: the empty state names the import, not an agent.
  emptyTitle: "No K-1s yet.",
  emptyBody: "K-1s appear here when the K-1 PDFs are imported from CCH Axcess.",
  superseded: "Superseded (amended K-1)",
} as const;
