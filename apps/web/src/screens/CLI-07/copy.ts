// CLI-07 copy, verbatim from the handoff (spec.md, revision.md R2 and the artboards a–g;
// docs/screens/CLI-07.md, Copy). Questionnaire sections, flag text and conditions are data from
// the firm's template and the record, never here. The refusal lines, the dialogs' words and the
// source-row kinds were written for P-07-T46 (DEC-431; listed in the contract).

const plural = (n: number, one: string, many: string): string =>
  `${String(n)} ${n === 1 ? one : many}`;

export const COPY = {
  back: (client: string) => `‹ ${client}`,
  backHint: (client: string) => `Opens CLI-02 · ${client}`,
  bar: {
    acceptance: (name: string) => `Acceptance — ${name}`,
    continuance: (name: string) => `Continuance — ${name}`,
    prepared: (person: string, date: string) => `Prepared by ${person} · ${date}`,
    preparedBy: (person: string) => `Prepared by ${person}`,
    questionnaire: (template: string) => `Questionnaire · ${template}`,
  },
  rail: {
    title: "Questionnaire",
    band: "Sections",
    acceptance: "Acceptance",
    continuance: "Continuance",
    sub: (person: string, n: number) =>
      `Prepared by ${person} · ${plural(n, "section", "sections")}`,
    awaiting: "Awaiting partner",
    notStarted: "Not started",
    conclusion: (word: string, initials: string) => `${word} · ${initials}`,
  },
  canvas: {
    title: "Pre-screen",
    requestCheck: "Request manual check…",
    addFlag: "Add flag…",
    review: "Request risk-partner review…",
    completeReview: "Complete review",
    running: (done: number, total: number) =>
      `Accrued Agent is screening · ${String(done)} of ${String(total)} sections`,
  },
  risk: {
    label: "Risk rating",
    rating: { low: "Low", moderate: "Moderate", high: "High" },
    flags: (n: number) => plural(n, "flag", "flags"),
    clear: (n: number, byCheck: number) =>
      `${plural(n, "section", "sections")} clear${byCheck > 0 ? ` (${String(byCheck)} by manual check)` : ""}`,
    open: (n: number) => `${plural(n, "manual check", "manual checks")} open`,
    awaiting: "conclusion awaiting partner",
    concluded: (word: string, person: string) => `conclusion: ${word} by ${person}`,
    notRequired: (rating: string) => `risk-partner review not required at ${rating}`,
    required: (rating: string) => `risk-partner review required at ${rating}`,
    requested: (person: string) => `risk-partner review requested of ${person}`,
    completed: (person: string) => `risk-partner review completed by ${person}`,
    nas: "see Independence (CLI-08) →",
    nasHint: (client: string) => `Opens CLI-08 · Independence · ${client}`,
  },
  severity: { low: "Low", medium: "Medium", high: "High" },
  flag: {
    makeCondition: "Make this a condition",
    arrow: "→",
    partnerCan: (partner: string) => `${partner} can make this a condition`,
    source: { evidence_version: "File", request_item: "Request" },
    sourceHint: "Opens SHL-08 · source viewer",
  },
  check: {
    open: (section: string) => `Manual check open · ${section}`,
    askedOf: (person: string, date: string) => `Asked of ${person} · ${date}`,
    complete: "Complete check…",
    completeTitle: (section: string) => `Complete the manual check · ${section}`,
    note: "Note",
    markDone: "Mark check done",
    requestTitle: "Request a manual check",
    section: "Section",
    person: "Ask",
    request: "Request check",
  },
  clear: (n: number) => `Clear sections (${String(n)})`,
  addFlag: {
    title: "Add a flag",
    flagTitle: "Title",
    severity: "Severity",
    body: "What it says",
    add: "Add flag",
  },
  review: {
    title: "Request a risk-partner review",
    partner: "Partner",
    request: "Request review",
  },
  dock: {
    title: "Decision",
    question: (client: string) => `Accept the ${client} engagement?`,
    continueQuestion: (client: string, period: string) =>
      `Continue the ${client} engagement for ${period}?`,
    accept: [
      { value: "accept", label: "Accept", detail: "Proceed to the engagement letter." },
      {
        value: "accept_with_conditions",
        label: "Accept with conditions",
        detail: "Add conditions from the flags.",
      },
      { value: "decline", label: "Decline", detail: "Record reasons; no letter." },
    ],
    continuance: (period: string) => [
      {
        value: "accept",
        label: "Continue",
        detail: `Proceed to the ${period} engagement letter.`,
      },
      {
        value: "accept_with_conditions",
        label: "Continue with conditions",
        detail: "Add conditions from the flags.",
      },
      { value: "decline", label: "Discontinue", detail: "Record reasons; no letter." },
    ],
    notReady: (count: number) => `Not ready for decision — ${String(count)} manual check open`,
    notReadyQuestionnaire: "Not ready for decision — questionnaire in progress",
    send: "Send to partner",
    decide: "Decide",
    partnerOnly: "Partner decision",
    rationaleLabel: "Rationale",
    reasons: "Reasons",
    continuanceNote: "Continuance note",
    conditions: "Conditions",
    conditionsDone: (done: number, total: number) => `${String(done)} of ${String(total)} done`,
    addCondition: "+ Add condition",
    condition: (n: number) => `Condition ${String(n)}`,
    removeCondition: (n: number) => `Remove condition ${String(n)}`,
    owner: (person: string, state: string) => `Owner ${person} · ${state}`,
    open: "Open",
    done: "Done",
    complete: (text: string) => `Mark done: ${text}`,
    reserved: (partner: string) =>
      `Reserved to ${partner} · Engagement partner. The decision date must precede the engagement letter (G1).`,
    recordedAccept: (at: string) =>
      `Decision recorded ${at} · it can't be edited. The engagement letter follows it (G1).`,
    recordedDecline: (at: string) =>
      `Decision recorded ${at} · it can't be edited. No engagement letter will be drafted.`,
    letter: "Draft engagement letter →",
    letterHint: (client: string) => `Opens ENG-04 · engagement letter · ${client}`,
    openClient: (client: string) => `Open ${client}`,
    decided: {
      accept: "Accepted",
      accept_with_conditions: "Accepted with conditions",
      decline: "Declined",
    },
    decidedLine: (partner: string, at: string) => `${partner} · ${at}`,
  },
  toast: { decided: "Decision recorded" },
  errors: {
    option: "Choose an option.",
    rationaleRequired: "A rationale is required.",
    conditions: "Add at least one condition.",
    stale: "This record changed since you opened it. Reload to see the latest.",
    locked: "The decision is already recorded.",
    notReady: "Not ready for decision",
    review: "A risk-partner review must be completed first.",
    invalid: "That person can't take this on here.",
    failed: "Couldn’t save. Try again.",
  },
  cancel: "Cancel",
  stepUp: {
    title: "Confirm it's you",
    body: "This action needs a recent sign-in. Sign in again, then try once more. If it still isn't allowed, your role doesn't permit it.",
    signIn: "Sign in again",
  },
} as const;
