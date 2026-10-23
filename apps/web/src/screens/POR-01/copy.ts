// POR-01 copy, verbatim from the handoff spec.md (docs/screens/POR-01.md, Copy). The firm's name,
// address, people and the email address are branding and session data, passed in. Keys marked
// "not handoff copy" are P-08-T09's own words for states the handoff has no frame for; they are
// recorded in the screen contract and keep the portal copy bans (no product name, no "password").

export const COPY = {
  a: {
    title: "Sign in to your client portal",
    body: (firm: string) =>
      `Use the email address ${firm} has on file. We'll send you a 6-digit code — no password needed.`,
    email: "Email",
    continue: "Continue",
    /** Not handoff copy: the spinner's name for assistive technology. */
    sending: "Sending your code",
  },
  footnote: (firm: string) => `${firm} uses secure sign-in. Codes expire after 10 minutes.`,
  footer: { help: "Help", privacy: "Privacy" },
  b: {
    title: "Check your email",
    body: (email: string) => `We sent a 6-digit code to ${email}.`,
    code: "Sign-in code",
    signIn: "Sign in",
    didntGet: "Didn't get it?",
    resend: "Resend code",
    differentEmail: "Use a different email",
  },
  c: { title: "Two-step verification" },
  e: {
    title: "This sign-in link has expired",
    body: "Links work for 14 days. We can send you a new one.",
    renew: "Email me a new link",
    toast: (email: string) => `New link sent to ${email}`,
  },
  f: {
    helper: (n: number) =>
      `That code didn't match. ${String(n)} ${n === 1 ? "try" : "tries"} left.`,
  },
  g: {
    title: "Too many attempts",
    body: (person: string, firm: string) =>
      `For your security, sign-in is paused for 15 minutes. If you need help now, contact ${person} at ${firm}.`,
    contact: (firm: string) => `Contact ${firm}`,
  },
  neutral: {
    /** Not handoff copy: an unknown portal host names no firm (the neutral branding answer). */
    body: "Use your email address. We'll send you a 6-digit code — no password needed.",
    footnote: "Codes expire after 10 minutes.",
    lockedBody: "For your security, sign-in is paused for 15 minutes.",
  },
  /** Not handoff copy: a landing whose screen is planned, in fixture builds only. */
  notBuilt: "Not built yet",
} as const;
