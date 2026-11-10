// AUD-19 · Completion (A-07-T25): every word verbatim from the handoff spec.

export const COPY = {
  title: "Completion",
  signOff: "Sign off…",
  openInExcel: "Open in Excel",
  tabs: {
    checklist: "Checklist",
    subsequent_events: "Subsequent events",
    legal_letters: "Legal letters",
    going_concern: "Going concern",
  },
  summary: {
    complete: (n: number) => `${String(n)} complete`,
    notApplicable: (n: number) => `${String(n)} not applicable`,
    open: (n: number) => `${String(n)} open`,
    of: (done: number, total: number) => `${String(done)} of ${String(total)}`,
  },
  blockers: {
    title: "What blocks the report",
    clear: "Nothing blocks the report — open Issuance & release",
  },
  notApplicable: "Not applicable",
  subsequent: {
    procedures: "Procedures",
    events: "Events found",
    columns: { event: "Event", type: "Type", effect: "FS effect", disclosure: "Disclosure" },
    recognition: { recognized: "Recognized", nonrecognized: "Nonrecognized" },
    bringDown: "Bring-down queued",
  },
  legal: {
    title: "Not applicable",
    request: "Request a legal letter…",
  },
  goingConcern: {
    question:
      "Is there substantial doubt about the plan's ability to continue as a going concern within one year after the financial statements are available to be issued?",
    // S31 close (DV-AUD-19-4): the same question for an FS audit's entity (Granite Peak).
    questionEntity:
      "Is there substantial doubt about the entity's ability to continue as a going concern within one year after the financial statements are available to be issued?",
    options: {
      no_substantial_doubt: "No substantial doubt",
      doubt_alleviated: "Substantial doubt alleviated by management's plans",
      doubt_exists: "Substantial doubt exists",
    },
    decided: (name: string, on: string) =>
      `Decided by ${name} · ${on} · Reserved to Engagement Partner`,
    reserved: "Reserved to Engagement Partner",
  },
} as const;
