// TAX-12 copy, verbatim from the handoff (screens/TAX-12 spec.md and the a2 artboard). Accrued
// records; the ERO transmits in CCH Axcess (R-04): no phrase here has Accrued or the agent file.

/** "federal, New York and Illinois": a jurisdiction list in a sentence. */
function list(names: readonly string[]): string {
  const words = names.map((n) => (n === "Federal" ? "federal" : n));
  return words.length < 2
    ? (words[0] ?? "")
    : `${words.slice(0, -1).join(", ")} and ${words[words.length - 1] ?? ""}`;
}

export const COPY = {
  rail: {
    title: "Delivery",
    card: "TY2025 delivery",
    // T-01-T51: the return's jurisdictions, from its payment instructions.
    sub: (names: readonly string[]) => names.join(" · "),
    awaiting: "Awaiting signature",
    inReview: "In review · Manager",
    band: "Checklist",
  },
  rows: {
    finalApproval: "Final approval",
    approvedBy: (name: string, when: string) => `Return approved by ${name} · ${when}`,
    blocked: (n: number) =>
      n === 1 ? "Blocked by 1 open item" : `Blocked by ${String(n)} open items`,
    exported: "Exported to tax engine",
    exportedSub: (when: string | null, engineId: string | null) =>
      [
        when === null ? "Not yet exported" : `Synced · ${when}`,
        ...(engineId ? [engineId] : []),
      ].join(" · "),
    diagnostics: "Engine diagnostics",
    diagnosticsSub: (errors: number, info: number) =>
      `${String(errors)} ${errors === 1 ? "error" : "errors"} · ${String(info)} informational`,
    packet: "Delivery packet",
    packetSub: (status: "draft" | "approved" | "superseded" | null) =>
      status === "approved" ? "Approved" : status === null ? "Not assembled yet" : "Draft",
    authorizations: "E-file authorizations",
    authorizationsSub: (signed: number, total: number, forms: string) =>
      `${String(signed)} of ${String(total)} signed${forms ? ` · ${forms}` : ""}`,
    payments: "Payment instructions",
    paymentsSub: (lines: readonly string[]) => lines.join(" · "),
    transmission: "Transmission",
    transmissionSub: "Locked until every signer signs",
    acks: "Acknowledgments",
    acksSub: "Not transmitted",
    delivery: "Client delivery",
    deliverySub: "After acceptance → portal Deliverables",
  },
  canvas: {
    title: "E-file authorizations",
    openEnvelope: "Open envelope",
    sendReminder: "Send reminder…",
    blockedTitle: "Delivery starts after final approval.",
    blockedBody: (approver: string | null, policy: string | null) =>
      `${approver ?? "The signing partner"} approves${policy ? ` under ${policy}` : ""}; the return is then exported to CCH Axcess.`,
  },
  envelope: {
    partly: "Partially signed",
    sent: (when: string | null, by: string | null, due: string | null) =>
      [
        when === null ? "Not sent yet" : `Sent ${when}${by ? ` by ${by}` : ""}`,
        ...(due ? [`due ${due}`] : []),
      ].join(" · "),
    signedLine: (kba: boolean, when: string) =>
      `${kba ? "KBA passed · " : ""}signed ${when} · IP and login logged`,
    viewedLine: (when: string) => `Viewed ${when} · identity check not started`,
    notViewed: "Not viewed yet",
    signed: "Signed",
    viewed: "Viewed",
    evidence:
      "Evidence kept per signer: signed image, date and time, IP address, login ID, KBA result, method (Pub. 1345). Retention: 3 years from the later of the due date or IRS received date.",
  },
  packet: {
    title: "Delivery packet",
    edit: "Edit packet",
    items: {
      client_copy: ["Client copy", "PDF"],
      filing_instructions_letter: ["Filing instructions letter", ""],
      form_8879_tr_579_it: ["Form 8879 + TR-579-IT", "In envelope"],
      voucher_1040es_q4: ["Form 1040-ES voucher", ""],
      voucher_it2105_q4: ["IT-2105 voucher", ""],
      engagement_invoice: ["Engagement invoice (from Billing)", "Sent separately"],
    } as Record<string, readonly [string, string]>,
  },
  payments: {
    title: "Payment instructions",
    // T-01-T51: one row per instruction, worded by code from its kind and jurisdiction.
    label: (jurisdiction: string, kind: "refund" | "balance_due" | "estimate") =>
      `${jurisdiction} ${{ refund: "refund", balance_due: "balance due", estimate: "estimate" }[kind]}`,
    value: (amount: string, due: string | null) => (due ? `${amount} · due ${due}` : amount),
    none: "No payment instructions yet.",
  },
  gate: {
    title: "Transmission",
    button: "Mark transmitted in CCH Axcess",
    body: "E-file is sent from CCH Axcess by the ERO. This stays locked until every signer completes Form 8879 — the taxpayer signs before the return is transmitted.",
    who: "Transmits: the ERO (Practitioner PIN)",
  },
  acks: {
    title: "Acknowledgments",
    none: "No acknowledgments yet.",
    accepted: (name: string) => `${name} return accepted`,
    submission: (last4: string) => `Submission ID ••••••${last4}`,
    rejected: (name: string, code: string, text: string) =>
      `${name} return rejected · ${code} — ${text}`,
  },
  // T-01-T39: the ERO's record (c, c2), acceptance (d) and rejection (e).
  ero: {
    waiting: "Waiting for the ERO to transmit",
    notify: "Notify",
    confirmTitle: "Mark transmitted",
    confirm: (names: readonly string[], on: string) =>
      `Record that the ${list(names)} returns were transmitted from CCH Axcess on ${on}?`,
    cancel: "Cancel",
    record: "Record transmission",
    recorded: "Transmission recorded",
  },
  status: { completed: "Completed", accepted: "Accepted", rejected: "Rejected" },
  delivered: "Delivered to portal",
  estimates: "Estimate reminders scheduled",
  fix: {
    body: "Jonah Feld's 2026 IP PIN is in the CP01A letter on file. Add it in CCH Axcess and retransmit.",
    create: "Create issue",
    created: "Issue created",
    failed: "The issue could not be created.",
  },
  editor: {
    title: "Delivery packet",
    regenerate: "Regenerate letter",
    approve: "Approve",
    include: (name: string) => `Include ${name}`,
  },
  syncHistory: "Tax-engine sync history",
  jurisdictions: { federal: "Federal", NY: "New York", IL: "Illinois", CO: "Colorado" } as Record<
    string,
    string
  >,
  reminder: {
    title: "Send reminder",
    toLabel: "To",
    recipient: (names: readonly string[]) => names.join(", "),
    channel: "Portal and email",
    template: "Template",
    templateName: "Your return is ready to sign",
    approved: "Pre-approved",
    // The reminder's words are the firm's pre-approved template (database content, P-06); the sheet
    // names who it goes to and what it does, never a fixture's letter.
    body: "The pre-approved reminder asks each signer who has not signed to review and sign in the portal.",
    footer: "Sent from the client portal",
    cancel: "Cancel",
    send: "Send",
    sent: "Reminder sent",
  },
} as const;
