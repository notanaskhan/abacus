// TPL-16 signing ceremony specimen copy (F-06-T01): verbatim from the handoff
// (screens/TPL-16, spec.md) with the chapter-09 rows applied: DF-11 replaces the
// verification-failed sentence, Q7 adds the ellipsis to the adopt label. White-labelled: the
// firm's name comes from the branding and the product's name never appears (DEC-01).

export const COPY = {
  title: "Form 8879 · TY2025 · Dev & Mira Kapoor",
  back: "All documents to sign",
  decline: "Decline…",
  download: "Download",
  documentsHeader: (n: number): string => `Documents (${n})`,
  form8879: "Form 8879 — IRS e-file Signature Authorization",
  formTr579: "Form TR-579-IT — New York e-file Signature Authorization",
  signersBand: "Signers",
  signerYou: (name: string): string => `${name} (you)`,
  steps: { verify: "Verify identity", review: "Review", sign: "Sign", done: "Done" },
  stepSubs: {
    verify: "4 of 4 questions · 9:21 AM",
    review: "2 documents",
    sign: "2 fields left on 2 documents",
  },
  signHere: "Sign here",
  pinPlaceholder: "Enter any five digits except all zeros",
  authorizingTitle: "What you're authorizing",
  // Q7: the action opens a step, so it carries the ellipsis (DECISIONS.md, F-06-T01).
  adoptAndSign: "Adopt signature & sign…",
  recordsNote: "Signing records the date, time, your IP address and the verification result.",
  nextDocument: "Next document →",
  completedTitle: (first: string): string => `Signed. Thank you, ${first}.`,
  evidenceLabels: {
    signed: "Signed",
    method: "Method",
    identity: "Identity",
    ip: "IP address",
    login: "Login",
    documents: "Documents",
  },
  willFile: (firm: string): string =>
    `${firm} will file your returns and message you when they're accepted.`,
  // DF-11: after three failed attempts remote signing closes for this form; no retry, no
  // countdown, no other method. Counsel confirms the Pub 1345 wording (DF-11).
  verifyFailedTitle: "We couldn't verify your identity.",
  verifyFailedBody: (firm: string, preparer: string): string =>
    `${firm} will send you a paper form to sign by hand. If you have questions, contact ${preparer} at ${firm}.`,
  declineTitle: "Decline to sign?",
  declineReasons: [
    "The amounts look wrong",
    "I have a question first",
    "Someone else should sign",
    "Other",
  ],
  declineNote: "Note",
  cancel: "Cancel",
  declineConfirm: "Decline",
  mobileStepChips: "Verify ✓ · Review ✓ · Sign · Done",
} as const;
