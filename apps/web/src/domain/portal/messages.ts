// Portal sign-in codes in words (ADR P-36: code → words; never a raw code on screen). The
// handoff words f ("That code didn't match. {n} tries left.") and g; the strings below are for the
// states the handoff has no frame for (docs/screens/POR-01.md, non-artboard states). They are
// written by P-08-T09 on the C-20 grammar (what happened, then what to do), not handoff copy, and
// keep the portal copy bans: no product name, no "password", no "task".

export const SIGN_IN_WORDS = {
  /** 410 `code_expired`: older than 10 minutes. */
  codeExpired: "That code has expired. Use Resend code to get a new one.",
  /** 429 `resend_too_soon`: the countdown restarts from the server's time. */
  resendTooSoon: "A new code can be sent when the countdown ends.",
  /** 503 `sign_in_paused`: the firm's kill switch (Story 7.3). */
  paused: (person: string, firm: string) =>
    `Sign-in is paused for now. If you need help, contact ${person} at ${firm}.`,
  pausedNoContact: "Sign-in is paused for now. Please try again later.",
  /** A request that never reached the server. */
  network: "We couldn't reach the sign-in service. Check your connection and try again.",
} as const;

/** Words for a failure code the code step shows under the boxes (f's helper grammar). */
export function failureWords(
  code: string,
  support: { person: string | undefined; firm: string },
): string | null {
  switch (code) {
    case "code_expired":
      return SIGN_IN_WORDS.codeExpired;
    case "resend_too_soon":
      return SIGN_IN_WORDS.resendTooSoon;
    case "sign_in_paused":
      return support.person === undefined || support.firm === ""
        ? SIGN_IN_WORDS.pausedNoContact
        : SIGN_IN_WORDS.paused(support.person, support.firm);
    case "network":
      return SIGN_IN_WORDS.network;
    default:
      return null;
  }
}

// POR-03 and POR-04 (R-01; docs/screens/POR-03.md, Copy): the receipts and lines the portal's
// documents draw from a code, verbatim from the handoff. Client words only: never a firm status,
// a match percentage, a confidence or the agent (glossary portal bans, R-01-T04).
const RETURN_REASON: Readonly<Record<string, string>> = {
  wrong_year: "wrong year",
  wrong_period: "wrong period",
};

export const DOCUMENT_WORDS = {
  receipt: {
    uploaded: (on: string) => `You uploaded ${on}`,
    emailed: (on: string) => `Received by email ${on}`,
    otherContact: (firstName: string, on: string) => `${firstName} uploaded ${on}`,
  },
  /** An open request's due day in the audit variant's bands (POR-03 i). */
  due: (on: string) => `Due ${on}`,
  /** A done request with no file the client can see (the firm received it another way). */
  done: "Done",
  firmProvided: (firm: string) =>
    `${firm} prepares this K-1 and adds it for you. Nothing to upload.`,
  providedByConnection: "Provided from your accounting system",
  uploadingN: (n: number) => `Uploading ${String(n)} files…`,
  /** The live region after a drop sorts (R-01 §5.6, key `live.sorted`). */
  sorted: (matched: number, unsorted: number, firm: string): string => {
    const files = (n: number): string => `${String(n)} ${n === 1 ? "file" : "files"}`;
    const parts = [
      ...(matched > 0 ? [`${files(matched)} matched a request.`] : []),
      ...(unsorted > 0 ? [`${files(unsorted)} sent to ${firm} to sort.`] : []),
    ];
    return parts.join(" ");
  },
  /** An upload the policy refused (413 `file_too_large`, 415 `type_not_allowed`; R-01-T10 writes
   * the words the handoff has no frame for, on the C-20 grammar: what happened, then what to do). */
  refused: {
    file_too_large: (name: string) =>
      `${name} is larger than 50 MB. Send a smaller copy or split it into parts.`,
    type_not_allowed: (name: string) =>
      `${name} can't be uploaded here. Send a PDF, a photo, a spreadsheet, a Word document or a CSV.`,
  },
  returned: {
    pill: (reason: string) => {
      const words = RETURN_REASON[reason];
      return words === undefined ? "Returned" : `Returned · ${words}`;
    },
  },
} as const;

// POR-04, the request sheet (R-01-T12; docs/screens/POR-04.md, Copy): verbatim from the handoff,
// templated where the data varies. The pre-check words are `ClientUploadChecks`' fixed words for
// a file of no known kind (DEC-58 e): no amount, no date the client did not send, no model text.
export const SHEET_WORDS = {
  header: { request: "Request", question: "Question", decision: "Decision" },
  upload: "Upload…",
  uploadCard: "Upload",
  why: "Why we need it",
  toDo: (requested: string) => `To do · requested ${requested}`,
  dropTitle: "Drop the file here",
  dropTypes: "PDF, JPG, PNG, HEIC, XLSX · up to 50 MB",
  lastYear: (file: string, on: string) => `Last year you sent ${file} on ${on}.`,
  comments: "Comments",
  visibility: (firm: string) => `Visible to you and ${firm}`,
  composer: "Write a comment…",
  send: "Send comment",
  notApplicable: "This doesn't apply to me…",
  ignoreTitle: "Why doesn't this apply?",
  /** The handoff names the request's firm person ("Kevin"); without one, the firm. */
  ignoreNote: (person: string) => `Add a note for ${person} (optional)`,
  ignoreSave: "Mark not applicable",
  ignored: (on: string) => `Marked not applicable · ${on}`,
  ignoredLine: "Marked not applicable",
  undo: "Undo",
  checkNext: (firm: string) => `${firm} will check it and let you know if anything is missing.`,
  withdraw: "Withdraw",
  withdrawConfirm: (firm: string) =>
    `Withdraw this file? ${firm}'s team won't use it. It's kept securely for 30 days, then erased.`,
  cancel: "Cancel",
  photo: "Take a photo",
  close: "Close",
  /** A returned file's note, quoted with its author and day. */
  returnedNote: (note: string | null | undefined, by: string, on: string) =>
    note == null || note === "" ? `— ${by}, ${on}` : `${note} — ${by}, ${on}`,
  preCheck: {
    wrong_period: "This file isn't for the year end.",
    stale_as_of: "This file isn't for the year end.",
    wrong_entity: "This looks like it's for a different company.",
    totals_dont_add_up:
      "The totals in this file don't add up. Please check it and upload it again.",
  },
  question: {
    send: "Send answer",
    answerLabel: "Your answer",
    textLabel: "Tell us more",
    answered: (at: string, by: string) => `You answered ${at} · ${by} will follow up if needed`,
  },
  decision: { send: "Send decision", choiceLabel: "Your decision" },
  sent: (firm: string) => `Sent to ${firm}`,
  // No handoff frame: written by R-01-T12 on the C-20 grammar (docs/screens/POR-04.md, Open gaps).
  notFound: "This request isn't available.",
  loadError: "Couldn’t load this request. Nothing was lost; try again in a moment.",
  retry: "Retry",
  loading: "Loading",
  failed: "That didn't go through. Nothing changed; try again in a moment.",
} as const;

// POR-14, the third-party room (R-01-T14; docs/screens/POR-14.md, Copy): verbatim from the
// handoff, templated where the data varies (the firm, the organisation, the dates).
const shortName = (organisation: string): string => organisation.split(" ")[0] ?? organisation;

export const ROOM_WORDS = {
  nav: "Requests",
  pane: "Requests",
  intro: (firm: string, organisation: string) =>
    `${firm} asked ${organisation} for these items. You can only see and upload to these requests.`,
  progress: (n: number, total: number) => `${String(n)} of ${String(total)} uploaded`,
  dropPill: "Drop files here",
  bandCount: (n: number, total: number) => `${String(n)} of ${String(total)}`,
  uploaded: (on: string) => `Uploaded ${on}`,
  due: (on: string) => `Due ${on}`,
  inReview: (on: string, firm: string) => `You uploaded ${on} · ${firm} is reviewing it`,
  /** The expanded row's upload slot: "letter" for a letter (the bridge letter), else "file". */
  uploadSlot: (title: string) =>
    `Drop the ${/\bletter\b/i.test(title) ? "letter" : "file"} here or Upload…`,
  comment: "Comment…",
  send: "Send comment",
  returnedNote: (note: string | null | undefined, by: string) =>
    note == null || note === "" ? `— ${by}` : `${note} — ${by}`,
  complete: (firm: string, organisation: string) =>
    `Everything ${firm} asked ${shortName(organisation)} for is in. Thank you.`,
  /** The chip: "Sam Ortiz · Keystone" (DEC-63: a named person, the organisation an attribute). */
  user: (name: string, organisation: string) =>
    organisation === "" ? name : `${name} · ${shortName(organisation)}`,
  expiredTitle: "This link has expired or was already used",
  expiredAction: (firm: string) => `Ask ${firm} for a new link`,
  pickerTitle: "Which request is this for?",
  pickerUpload: "Upload",
  cancel: "Cancel",
  signOut: "Sign out",
  userMenu: "Account",
  // No handoff frame: written by R-01-T14 on the C-20 grammar (docs/screens/POR-14.md, Open gaps).
  loading: "Loading",
  loadError: "Couldn’t load your requests. Nothing was lost; try again in a moment.",
  retry: "Retry",
  failed: "That didn't go through. Nothing changed; try again in a moment.",
} as const;
