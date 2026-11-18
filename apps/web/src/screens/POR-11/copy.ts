// POR-11 copy (C-01-T41, DEC-5638): the client's words only, verbatim from the handoff (POR-11
// spec and POR-04 frame e). No firm words: never "Pending incorporation", "Matched to uploaded
// document", "Visible to client" or a review count (QC-9).
export const COPY = {
  questions: (n: number) => `Transaction questions · ${n} to answer`,
  answer: "Answer…",
  answerMobile: "Answer",
  answered: (when: string) => `✓ You answered ${when}`,
  sheet: {
    title: "Answer the question",
    choices: {
      lost_reissue: "Lost — please reissue it",
      voided: "Voided",
      something_else: "Something else",
    },
    note: "Add a note",
    send: "Send answer",
    cancel: "Cancel",
  },
  loading: "Loading your close",
} as const;
