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
