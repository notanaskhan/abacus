// POR-23's words, verbatim from the handoff (POR-23 a, b; docs/screens/POR-23.md). Client words
// only: Due · ✓ You uploaded · Overdue · Returned. "Accrued" never appears (portal rule 7).
export const COPY = {
  nav: "Group audit",
  header: "Group audit",
  component: (name: string): string => `Component: ${name}`,
  intro: (firm: string): string =>
    `${firm} is the group auditor. This room holds the instructions, deliverables and questions for your component only.`,
  progress: (uploaded: number, total: number): string =>
    `${String(uploaded)} of ${String(total)} deliverables`,
  drop: "Drop files here",
  instructions: "Instructions",
  instructionsTitle: "Group audit instructions",
  sentOn: (on: string): string => `Sent ${on}`,
  acknowledged: (on: string): string => `✓ You acknowledged ${on}`,
  acknowledge: "Acknowledge instructions",
  ask: "Ask a question",
  acknowledgeNote:
    "Acknowledging confirms that you received these instructions and will follow them, or will tell us promptly if you cannot.",
  confirmTitle: (component: string): string => `Acknowledge the instructions for ${component}?`,
  cancel: "Cancel",
  confirm: "Acknowledge",
  deliverables: (uploaded: number, total: number): string =>
    `Deliverables · ${String(uploaded)} of ${String(total)}`,
  word: {
    due: (on: string): string => `Due ${on}`,
    you_uploaded: (on: string): string => `✓ You uploaded ${on}`,
    overdue: (on: string): string => `Overdue · due ${on}`,
    returned: "Returned",
  },
  upload: "Upload…",
  questions: "Questions",
  noQuestions: (firm: string): string => `No questions yet. Questions go to ${firm}.`,
  composer: (firm: string): string => `Ask ${firm} a question…`,
  expired: "This invitation has expired",
  expiredBody: "Ask the group auditor to send you a new invitation.",
} as const;
