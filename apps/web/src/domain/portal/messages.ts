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
