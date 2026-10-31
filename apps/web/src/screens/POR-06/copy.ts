// POR-06 Sign copy (N-02-T26; docs/screens/POR-06.md "Copy"; handoff POR-06 spec). Verbatim from
// the handoff where it draws the words, with the chapter-09 rows applied (DF-11, DF-12). White
// label: the firm's name comes from the branding and the product's name never appears (DEC-01).
// Words no artboard draws are marked "(DEC-1251)".

export const COPY = {
  nav: "Sign",
  back: "All documents",
  listTitle: "To sign",
  signedBand: "Signed",
  // (DEC-1251) the list's empty state.
  nothingToSign: "Nothing to sign right now.",
  due: (day: string): string => `Due ${day}`,
  continue: "Continue to sign",
  // (DEC-1251) why Continue waits: the last page must be read first.
  continueHint: (last: number): string => `Read to page ${String(last)} to continue.`,
  steps: { verify: "Verify identity", review: "Review", sign: "Sign", done: "Done" },
  stepSubs: {
    // The portal's own sign-in verified the person by email code (DF-11: letters and consents).
    verify: "Email code",
    // N-02-T29 (POR-06d, DF-11, DF-12): the 8879 family verifies by identity questions, which the
    // provider asks in its own view.
    kba: "Identity questions",
    // POR-06f: the server's date gate (`signing_opens_on`).
    opens: (day: string): string => `Opens ${day}`,
    reviewing: (page: number, total: number): string => `Page ${String(page)} of ${String(total)}`,
    reviewed: (total: number): string => `${String(total)} ${total === 1 ? "page" : "pages"}`,
  },
  consent: {
    title: "Agree to sign electronically",
    agree: "I agree to sign electronically and that my electronic signature is binding",
    // (DEC-1251) the consent's call to action.
    confirm: "Agree and continue",
  },
  completedTitle: (first: string): string => `Signed. Thank you, ${first}.`,
  // (DEC-1251) the completion card's note while another signer is still to sign.
  waiting: (n: number): string =>
    `Waiting for ${String(n)} more ${n === 1 ? "signature" : "signatures"}.`,
  evidenceLabels: { fingerprint: "Document fingerprint", signers: "Signers" },
  fingerprint: (sha: string): string => `SHA-256 ${sha.slice(0, 4)}…${sha.slice(-4)}`,
  signedOf: (signed: number, total: number): string =>
    `${String(signed)} of ${String(total)} signed`,
  fieldLabels: { signature: "signature", pin: "PIN", date: "date" },
  decline: {
    trigger: "Decline…",
    title: "Decline to sign?",
    reasonsLabel: "Why are you declining?",
    reasons: ["I have questions", "Something is wrong", "Someone else should sign", "Other"],
    note: "Note",
    confirm: "Decline",
  },
  // (DEC-1251) undoing a decline (C7 `decline/withdraw`).
  withdraw: "Withdraw decline",
  restrictedTitle: "You aren't a signer on this envelope.",
  restrictedBody: (firm: string): string => `Ask ${firm} who should sign it.`,
  loadError: "This envelope didn't load.",
  retry: "Try again",
  failed: "That didn't go through. Try again.",
  // F-06-T05's words for the provider's view, the return and DF-11 (TPL-16 copy).
  providerTitle: (document: string): string => `Sign: ${document}`,
  providerContinue: "Continue to sign",
  providerUnavailable: "Signing isn't available right now. Try again in a few minutes.",
  pendingTitle: "Checking your signature",
  pendingBody: "This page updates as soon as your signature is recorded.",
  verifyFailedTitle: "We couldn't verify your identity.",
  verifyFailedBody: (firm: string): string => `${firm} will send you a paper form to sign.`,
  stepNames: { verify: "Verify", review: "Review", sign: "Sign", done: "Done" },
  // N-02-T29, POR-06d: the authorizing card on an e-file authorization (handoff d's note under the
  // identity questions; DF-12 moves the questions into the provider's view).
  kbaCard: {
    title: "Identity questions",
    body: "IRS rules require identity verification before you sign an e-file authorization remotely. Questions come from public records; your answers aren't stored.",
  },
  // POR-06e: a joint return's other spouse signs with a link of their own. (DEC-1388: the
  // handoff's "Jonah gets his own link." without the pronoun.)
  separately: (other: string): string =>
    `Each spouse verifies and signs separately. ${other} has a separate link.`,
  // POR-06f: the dated letter's note. (DEC-1388: the handoff's "we'll send a reminder that
  // morning" is left out; no reminder is scheduled on the letter's date.)
  datedNote: (day: string, firm: string): string =>
    `This letter is dated ${day} — the date of ${firm}'s report. Please sign on that date.`,
  // (DEC-1388) the signers card's lines: the server's status and role in client words.
  signer: {
    signed: (when: string): string => `Signed ${when}`,
    toSign: "To sign",
    separate: "Separate link",
    ero: (firm: string): string => `ERO · ${firm}`,
    countersigns: (firm: string): string => `Countersigns · ${firm}`,
    declined: "Declined",
    paperForm: "Needs a handwritten signature",
  },
  signOut: "Sign out",
  userMenu: "Account",
} as const;
