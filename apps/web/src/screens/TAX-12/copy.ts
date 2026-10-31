// TAX-12 copy, verbatim from the handoff (screens/TAX-12 spec.md and the a2 artboard). Accrued
// records; the ERO transmits in CCH Axcess (R-04): no phrase here has Accrued or the agent file.

export const COPY = {
  rail: {
    title: "Delivery",
    card: "TY2025 delivery",
    sub: "Federal · NY + NYC · IL · CO",
    awaiting: "Awaiting signature",
    inReview: "In review · Manager",
    band: "Checklist",
  },
  rows: {
    finalApproval: "Final approval",
    approvedBy: (name: string, when: string) => `Return approved by ${name} · ${when}`,
    blockedK1: "Blocked by Draft K-1 · pre-release (Ridgeline releases Sep 15)",
    exported: "Exported to tax engine",
    exportedSub: "Synced · Sep 16, 11:42 AM · 2025I:FeldJ:V3",
    diagnostics: "Engine diagnostics",
    diagnosticsSub: "0 errors · 2 informational",
    packet: "Delivery packet",
    packetSub: "Assembled by Accrued Agent · approved by Grace Holloway",
    authorizations: "E-file authorizations",
    authorizationsSub: (signed: number, total: number) =>
      `${String(signed)} of ${String(total)} signed · Form 8879 + NY TR-579-IT`,
    payments: "Payment instructions",
    paymentsSub: "Federal refund 253 · NY balance due 1,269",
    transmission: "Transmission",
    transmissionSub: "Locked until both spouses sign",
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
    blockedBody: "Daniel Reyes approves under BH-TAX-02; Samuel Ito then exports to CCH Axcess.",
  },
  envelope: {
    partly: "Partially signed",
    sent: "Sent Sep 16, 1:05 PM by Grace Holloway · due Sep 30",
    claire: "KBA passed 4 of 4 · signed Sep 16, 7:48 PM · IP and login logged",
    jonah: "Viewed Sep 17, 8:02 AM · identity check not started",
    signed: "Signed",
    viewed: "Viewed",
    evidence:
      "Evidence kept per signer: signed image, date and time, IP address, login ID, KBA result, method (Pub. 1345). Retention: 3 years from the later of the due date or IRS received date.",
  },
  packet: {
    title: "Delivery packet",
    edit: "Edit packet",
    items: {
      client_copy: ["Client copy — federal, NY, IL, CO", "PDF · 64 pages · 2.8 MB"],
      filing_instructions_letter: [
        "Filing instructions letter",
        "Federal refund by direct deposit; NY balance due 1,269 with the return; 2026 estimates",
      ],
      form_8879_tr_579_it: ["Form 8879 + TR-579-IT", "In envelope"],
      voucher_1040es_q4: ["2026 Form 1040-ES voucher — Q4 Jan 15, 2027 · 19,990", ""],
      voucher_it2105_q4: ["2026 IT-2105 voucher — Q4 Jan 15, 2027 · 7,824", ""],
      engagement_invoice: ["Engagement invoice (from Billing)", "Sent separately"],
    } as Record<string, readonly [string, string]>,
  },
  payments: {
    title: "Payment instructions",
    rows: [
      ["Federal refund", "253 · direct deposit · Claire Feld checking ••6620"],
      [
        "New York (IT-201 incl. NYC)",
        "1,269 due · pay with the return via NY Online Services (interest from Apr 15)",
      ],
      ["Illinois (IL-1040, nonresident)", "0 · PTET credit 7,011 equals the tax"],
      ["Colorado (DR 0104PN)", "0 · PTET credit 4,268 covers the tax"],
      [
        "2026 estimates",
        "19,990 per quarter federal · 7,824 NY (both 110% of 2025 tax) · Q3 paid Sep 15",
      ],
    ] as const,
  },
  gate: {
    title: "Transmission",
    button: "Mark transmitted in CCH Axcess",
    body: "E-file is sent from CCH Axcess by the ERO. This stays locked until every signer completes Form 8879 — the taxpayer signs before the return is transmitted.",
    who: "Transmits: Daniel Reyes (ERO, Practitioner PIN)",
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
    waiting: "Waiting for Daniel Reyes to transmit",
    notify: "Notify",
    confirmTitle: "Mark transmitted",
    confirm:
      "Record that the federal, New York, Illinois and Colorado returns were transmitted from CCH Axcess on Sep 18, 2026?",
    cancel: "Cancel",
    record: "Record transmission",
    recorded: "Transmission recorded",
  },
  status: { completed: "Completed", accepted: "Accepted", rejected: "Rejected" },
  delivered: "Delivered to portal · Sep 19, 9:10 AM",
  estimates: "2026 estimate reminders scheduled",
  fix: {
    body: "Jonah Feld's 2026 IP PIN is in the CP01A letter on file. Add it in CCH Axcess and retransmit.",
    create: "Create issue",
  },
  editor: {
    title: "Delivery packet",
    regenerate: "Regenerate letter",
    approve: "Approve",
    include: (name: string) => `Include ${name}`,
  },
  jurisdictions: { federal: "Federal", NY: "New York", IL: "Illinois", CO: "Colorado" } as Record<
    string,
    string
  >,
  reminder: {
    title: "Send reminder",
    toLabel: "To",
    recipient: "Jonah Feld (taxpayer)",
    channel: "Portal and email",
    template: "Template",
    templateName: "Your 2025 return is ready to sign",
    approved: "Pre-approved",
    body: "Hi Jonah, your 2025 federal and state returns are ready for your signature. Claire signed on September 16. Please review and sign Form 8879 and NY TR-579-IT in your portal by September 30.",
    signature: "Grace Holloway · Brightwater Hale LLP",
    footer: "Sent as Grace Holloway from the client portal",
    cancel: "Cancel",
    send: "Send",
    sent: "Reminder sent to Jonah Feld",
  },
} as const;
