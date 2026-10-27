// T16 signing ceremony template copy (F-06-T01): the template board's placeholder strings
// (screens/T16), shown on Claire Feld's e-file authorizations. The seeded specimen copy is
// TPL-16's. White-labelled (DEC-01).

export const COPY = {
  documentsHeader: (n: number): string => `Documents (${String(n)})`,
  signersBand: "Signers",
  steps: { verify: "Verify identity", review: "Review", sign: "Sign", done: "Done" },
  signHere: "Sign here",
  authorizingTitle: "What you're authorizing",
  recordsNote: "Signing records the date, time, your IP address and the verification result.",
  signedCount: (signed: number, total: number): string =>
    `${String(signed)} of ${String(total)} signed`,
} as const;
