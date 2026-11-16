// AUD-35 Component auditors (A-09-T22): every word as the handoff writes it (AUD-35 spec, states
// a to g). Nothing here is invented; figures match AUD-34 (component PM 105,000, CT 12,000).
export const COPY = {
  title: "Component auditors",
  add: "+ Add component auditor",
  bandFull: "Full scope · 1",
  bandGroup: "Group team · 4",
  groupNote: "Manufacturing · Real Estate · Holdings · Operating Co. — no component auditor",
  auditor: "Pruett & Lang LLP",
  where: "Houston, TX · Harlow & Pike Distribution, Inc.",
  detailTitle: "Pruett & Lang LLP — Harlow & Pike Distribution, Inc.",
  kv: [
    ["Engagement partner", "Renee Pruett"],
    ["Component", "Harlow & Pike Distribution, Inc. · Houston, TX · level 3"],
    ["Planned work", "Full scope"],
    ["Component performance materiality", "105,000"],
    ["Threshold for communicating misstatements", "12,000 (group CT)"],
    ["Portal access", "Renee Pruett · invited with the instructions · this component only"],
  ],
  makeReferenceOff: "No — Brightwater Hale takes responsibility for Pruett & Lang's work",
  makeReferenceBanner:
    "Making reference: the group auditor's report will refer to Pruett & Lang's audit, and the component's financial statements must be audited under GAAS. The engagement partner decides.",
  competence: [
    ["Questionnaire", "Received Sep 10 ✓"],
    ["Professional competence and resources", "Evaluated by Omar Haddad · Sep 14"],
    ["Independence and ethics", "Confirmed in questionnaire §3 · Sep 10"],
    ["Peer review report", "Obtained · no deficiencies"],
  ],
  sections: [
    "§1 Scope and component",
    "§2 Timetable and deliverables",
    "§3 Independence and ethics",
    "§4 Materiality — component PM 105,000; threshold 12,000",
    "§5 Significant risks",
    "§6 Required communications",
    "§7 Access to documentation",
  ],
  needsInput: "Needs input — the group risk assessment is not done yet",
  risksDone:
    "Revenue cut-off at dealer shipments · inventory valuation · intercompany purchases from Manufacturing",
  provenance: "Drafted by Omar Haddad via Agent · 4:12 PM from the scoping decision (3:40 PM)",
  openLetter: "Open letter ›",
  steps: ["Draft", "Sent", "Acknowledged"],
  deliverables: [
    ["Planning confirmation", "Oct 2, 2026"],
    ["Interim memo", "Nov 30, 2026"],
    [
      "Clearance memo, summary of uncorrected misstatements and component trial balance",
      "Feb 12, 2027",
    ],
    ["Subsequent events update through the group report date", "Mar 19, 2027"],
  ],
  send: "Send instructions…",
  sendBlocked: "Complete §5 first",
  request: "Request deliverable…",
  preview: "Preview as Pruett & Lang",
  footerNote:
    "Instructions go through the component auditor room (POR-23); no signature envelope is needed.",
  questions: [
    [
      "Renee Pruett · Sep 23, 9:52 AM",
      "Is component PM based on the component's own benchmark or allocated from group?",
    ],
    [
      "Omar Haddad · Sep 23, 11:15 AM",
      "Allocated from group PM 180,000, weighted by component risk; see instructions §4.",
    ],
  ],
  followUp:
    "Draft follow-up to Renee Pruett: Your interim memo for Harlow & Pike Distribution, Inc. was due November 30. Please upload it to the group audit room or tell us when to expect it.",
  toast: "Follow-up sent to Renee Pruett · 8:52 AM",
} as const;

/** The only deliverable status words (addendum §3.2). */
export const DELIVERABLE_STATUSES = ["Expected", "Received", "Reviewed", "Late"] as const;
