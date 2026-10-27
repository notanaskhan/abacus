// CLI-08 copy, verbatim from the handoff spec.md (docs/screens/CLI-08.md, Copy). Names, roles,
// statements and dates are data, never copy.

export const COPY = {
  title: "Independence & conflicts",
  standards: "Standards · AICPA ET 1.200 · DOL 29 CFR 2509.75-9",
  tabs: {
    label: "Independence & conflicts",
    conflicts: "Conflicts",
    nas: "NAS matrix",
    team: "Team confirmations",
    rotation: "Rotation",
  },
  subbar: {
    count: (confirmed: number, total: number) =>
      `${String(confirmed)} of ${String(total)} confirmed`,
  },
  banner: {
    pending: (person: string, engagement: string) =>
      `${person} has not confirmed independence. They cannot be assigned or sign off on ${engagement} workpapers until they do (G2).`,
    self: (engagement: string) => `Confirm your independence for ${engagement}`,
    breach: "Breach logged — evaluate, communicate to TCWG, remediate",
    declined: (person: string) =>
      `${person} declined to confirm independence. They stay blocked from assignment and sign-off until the engagement partner resolves it.`,
    why: "Why?",
  },
  reminder: { send: "Send reminder", sent: (person: string) => `Reminder sent to ${person}` },
  team: {
    search: "Search people",
    confirmMine: "Confirm my independence",
    footer:
      "Each person confirms their own independence; no one can confirm for someone else. Confirmations must precede their first sign-off.",
    columns: {
      person: "Person",
      role: "Role on engagement",
      annual: "Annual firm confirmation",
      engagement: "This engagement",
      interests: "Interests check",
      confirmed: "Confirmed",
    },
    pill: { confirmed: "✓ Confirmed", pending: "Pending", declined: "Declined" },
    requested: (reminders: number) =>
      reminders === 0
        ? "Requested"
        : `Requested · ${String(reminders)} reminder${reminders === 1 ? "" : "s"}`,
    interests: "Statements confirmed",
    declinedNote: "Note to the engagement partner",
    none: "—",
  },
  roles: {
    engagement_partner: "Engagement partner",
    eqr_reviewer: "EQR reviewer",
    manager: "Manager",
    senior: "Senior (in-charge)",
    staff: "Staff",
    specialist: "Specialist",
  } as Readonly<Record<string, string>>,
  conclude: {
    button: "Conclude…",
    reserved: (partner: string, pending: number) =>
      pending > 0
        ? `Reserved to ${partner} · ${String(pending)} confirmation${pending === 1 ? "" : "s"} pending`
        : `Reserved to ${partner}`,
    title: "Conclude engagement independence?",
    options: {
      independent: "Independent",
      independent_with_safeguards: "Independent with safeguards",
      not_independent: "Not independent",
    },
    detail: {
      independent: "No threats to independence were identified.",
      independent_with_safeguards: "Threats were reduced to an acceptable level by safeguards.",
      not_independent: "The firm is not independent of this client for this engagement.",
    },
    safeguards: "Safeguards",
    confirm: "Conclude",
    cancel: "Cancel",
    note: "Only the engagement partner concludes, with a recent sign-in.",
    concluded: (partner: string, date: string) => `Concluded · ${partner} · ${date}`,
  },
  self: {
    title: (engagement: string) => `Confirm your independence for ${engagement}`,
    confirm: "Confirm",
    decline: "Decline…",
    declineTitle: "Decline to confirm",
    declineNote: "Note to the engagement partner",
    declineSend: "Decline",
    cancel: "Cancel",
    toast: (when: string) => `Independence confirmed · ${when}`,
  },
  nas: {
    columns: {
      service: "Service",
      provided: "Provided?",
      evaluation: "Evaluation (ET 1.295)",
      ske: "SKE designee",
      safeguards: "Safeguards / documentation",
      status: "Status",
    },
    provided: "Provided",
    notProvided: "Not provided",
    nonAttest: "Non-attest client: no SKE designation required",
    card: (preparer: string, partner: string) =>
      `Engagement independence · prepared by ${preparer} · to be concluded by ${partner}`,
    pending: (n: number) => `Pending ${String(n)} team confirmation${n === 1 ? "" : "s"}`,
  },
  conflicts: {
    line: (names: number, at: string) =>
      `Searched ${String(names)} names across every client, entity, contact and counterparty · ${at}`,
    columns: {
      match: "Match",
      kind: "Match kind",
      assessment: "Assessment",
      cleared: "Cleared by",
    },
    kinds: {
      exact: "Exact name",
      trigram: "Similar name",
      relationship: "Related party",
      counterparty: "Counterparty",
    },
    restricted: "Restricted match",
    clean: "No conflicts",
    noted: (n: number) => `No conflicts · ${String(n)} related party noted`,
    none: "No conflict check yet",
    noneBody: "Run the conflict check from the client's intake.",
  },
  rotation: {
    note: (years: number) =>
      `No rotation requirement for nonissuer audits; the firm evaluates familiarity threat after ${String(years)} consecutive years.`,
    columns: {
      person: "Person",
      role: "Role",
      years: "Years served",
      threat: "Threat evaluation",
    },
    flagged: "Familiarity threat to evaluate",
  },
  notFound: "This engagement isn't available.",
  failed: "Couldn’t save that",
} as const;
