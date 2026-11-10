// POR-15's words, verbatim from the handoff (screens/POR-15 spec.md; docs/screens/POR-15.md Copy).
// Every letter, date, name and report is the server's; the firm's name is the brand's.

export const COPY = {
  communications: "Communications",
  reports: "Reports",
  questions: "Questions for you",
  committee: "Committee",
  chair: "Chair",
  member: "Member",
  notYetAcknowledged: "Not yet acknowledged",
  acknowledgedOn: (day: string) => `Acknowledged ${day}`,
  acknowledgedByCommittee: (day: string) => `Acknowledged by the committee · ${day}`,
  sentOn: (day: string) => `Sent ${day}`,
  expected: (day: string) => `Expected · ${day}`,
  due: (sent: string, due: string) => `Sent ${sent} · due ${due}`,
  downloadPdf: "Download PDF",
  download: "Download",
  pages: (n: number) => `${String(n)} pages`,
  members: (body: string, subject: string) => `Members of the ${body} · ${subject}`,
  ackLine: "Acknowledging confirms you've received and read this letter.",
  acknowledge: "Acknowledge",
  askAuditor: "Ask the auditor…",
  send: "Send",
  cancel: "Cancel",
  privacy: (firm: string) =>
    `Your answers go only to the ${firm} audit team. Other committee members and plan management can't see them.`,
  sendAnswers: "Send answers",
  answersSent: "Answers sent",
  empty: "Nothing from your auditor yet.",
  emptyBody: "Planning communications usually arrive before fieldwork.",
  noReports: "No reports yet.",
  // The designed flag-off and not-allowed state (DEC-93: a room the grant does not open is 404).
  notOn: "The governance room is not open for you.",
  changed: "This letter changed. Showing the current version.",
  downloadFailed: "The download didn't finish. Try again.", // POR-13's words
} as const;
