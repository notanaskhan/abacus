// SHL-20 copy (docs/screens/SHL-20.md "Copy"; handoff SHL-20 spec.md, verbatim). The C-34 labels
// (title, verdict words, questions, Flagged files, View, Return…) live in the kit.
export const SCREENING_COPY = {
  chip: {
    flagged: (n: number): string => `Screening · ${String(n)} flagged`,
    passed: "Screening · passed",
    notScreened: "Screening · not screened",
  },
  request: (title: string, period: string | null): string =>
    period === null ? title : `${title} · expected period ${period}`,
  footer: {
    draftFollowUp: "Draft follow-up",
    rerun: "Rerun",
    screenNow: "Screen now",
    link: "Link to request…",
    linkHint: "Opens INB-02 · filing for this file",
  },
  provenance: (prompt: string | null, seconds: number | null): string =>
    [
      "Screened by Accrued Agent",
      ...(prompt === null ? [] : [prompt]),
      ...(seconds === null ? [] : [`${String(seconds)} s`]),
      "instructions inside files are never followed",
    ].join(" · "),
  running: (n: number): string => `Screening ${String(n)} new files…`,
  passedTotal: (n: number, of: number): string =>
    `${String(n)} of ${String(of)} payments supported`,
  notScreened: {
    body: "Screening has not run on this file. It runs once the file is linked to a request.",
  },
  // The answers, worded by code from the aggregate (DEC-351, DV-2).
  answers: {
    documentFlag: (answering: number, total: number): string =>
      `${String(answering)} of ${String(total)} files answer the request. ${String(total - answering)} do not.`,
    documentPass: (total: number): string => `All ${String(total)} files answer the request.`,
    periodPassOthers: (period: string): string => `All other files are dated inside ${period}.`,
    periodPass: (period: string): string => `All files are dated inside ${period}.`,
    periodFlag: (n: number, period: string): string =>
      n === 1
        ? `1 file is dated outside ${period}.`
        : `${String(n)} files are dated outside ${period}.`,
    notRun: "Not checked yet.",
  },
  feedback: {
    helpful: "Helpful",
    notHelpful: "Not helpful",
    title: "Why?",
    reasons: {
      wrong_request_match: "Wrong request match",
      wrong_period: "Wrong period",
      unclear_file: "Unclear file",
      other: "Other",
    },
    note: "Note",
    send: "Send feedback",
    sent: (reason: string): string => `Feedback sent · ${reason}`,
    sentUp: "Feedback sent",
    failed: "Couldn’t send the feedback",
  },
  sheet: {
    title: (name: string): string => `Follow-up to ${name}`,
    // "POR-04 comment · SURL request": the request's short name, its trailing "(…)" when it has one.
    context: (short: string): string => `POR-04 comment · ${short} request`,
    tag: "Drafted by Accrued Agent · edit before sending",
    body: (name: string): string => `Message to ${name}`,
    returning: (file: string): string => `Returning: ${file}`,
    cancel: "Cancel",
    send: (name: string): string => `Send to ${name}`,
    footnote: (n: number): string =>
      `Sends in the portal and by email. ${
        n === 1 ? "The file shows" : n === 2 ? "Both files show" : `All ${String(n)} files show`
      } Returned.`,
    sent: (name: string): string => `Follow-up sent to ${name}`,
    failed: "Couldn’t draft the follow-up",
    sendFailed: "Couldn’t send the follow-up",
  },
  rerunFailed: "Couldn’t rerun the screening",
  rerunBusy: "A screening of these files is still running",
} as const;
