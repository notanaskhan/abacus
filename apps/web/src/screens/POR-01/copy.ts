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
  c: {
    title: "Two-step verification",
    body: "Enter the 6-digit code from your authenticator app.",
    code: "Authenticator code",
    trust: "Trust this device for 30 days",
    verify: "Verify",
    backup: "Use a backup code",
    /** Not handoff copy (P-08-T19): the backup-code entry the ghost button opens. */
    backupBody: "Enter one of the backup codes you saved when you set up two-step verification.",
    backupField: "Backup code",
    useApp: "Use your authenticator app",
    /** Not handoff copy: an `mfa_token` that is used up or older than 5 minutes. */
    expired: "That step has expired. Sign in again to get a new code.",
    /** Not handoff copy: the identity provider didn't answer (503 `mfa_unavailable`). */
    unavailable: "We couldn't check that code just now. Try again in a minute.",
  },
  /** c′, the DF-17 two-step setup state (no handoff frame): not handoff copy (P-08-T19). */
  setup: {
    title: "Set up two-step verification",
    body: (firm: string) =>
      `${firm} asks for a second step when you sign in. Add this account to your authenticator app, then enter the 6-digit code it shows.`,
    bodyNeutral:
      "A second step is needed when you sign in. Add this account to your authenticator app, then enter the 6-digit code it shows.",
    open: "Open in your authenticator app",
    key: "Or enter this key",
    verify: "Verify",
    codesTitle: "Save your backup codes",
    codesBody:
      "Each code works once if you can't use your authenticator app. Keep them somewhere safe: this is the only time they are shown.",
    codesList: "Backup codes",
    saved: "I've saved these codes",
    done: "Continue",
  },
  d: {
    title: (firm: string) => `${firm} invited you`,
    body: (firm: string, plan: string, org: string, n: number) =>
      `${firm} is auditing the ${plan} and has asked ${org} for ${String(n)} items. You'll only see those requests.`,
    email: "Email",
    name: "Name",
    organization: "Organization",
    access: "Access",
    delegated: "Requests delegated to you",
    /** Not handoff copy: an invitation that is not a delegation (a firm or colleague invite). */
    bodyScope: (firm: string, scope: string) =>
      `${firm} invited you to its client portal for ${scope}.`,
    terms: (firm: string) => `${firm} client portal terms`,
    agree: "I agree to the",
    accept: "Accept and continue",
    /** Not handoff copy: a preview or acceptance that answers 404 (one answer for every failure). */
    invalidTitle: "This invitation can't be used",
    invalid: (firm: string) =>
      `This invitation link can't be used. Ask ${firm} to send you a new one.`,
    invalidNeutral: "This invitation link can't be used. Ask for a new one.",
  },
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
