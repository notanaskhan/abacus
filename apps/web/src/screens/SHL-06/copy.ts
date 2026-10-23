// SHL-06 copy (P-01-T11; docs/screens/SHL-06.md, Copy). g is the handoff's frames 1 and 7
// verbatim; the error state is undesigned (T15 error grammar), its words are recorded in the
// screen contract.

export const COPY = {
  title: "Sign in to Accrued",
  signingIn: "Signing in…",
  links: ["Privacy", "Terms", "System status"],
  error: {
    title: "Sign-in didn't complete",
    retry: "Sign in again",
    /** By the BFF's refusal code (`/signin/callback?error=`) or the refresh's 401 detail. */
    reasons: {
      mfa_required_at_sign_in:
        "Your sign-in needs a second factor. Turn on two-step verification with your sign-in provider, then sign in again.",
      unknown_staff_user:
        "This sign-in isn't linked to anyone at your firm. Ask your firm's administrator for an invitation.",
      session_expired: "Your session ended. Sign in again to carry on.",
      session_refresh_reused: "For your security, this session was ended. Sign in again.",
      session_rejected: "Your sign-in wasn't accepted. Try again, or ask your firm's IT team.",
      sign_in_failed: "The response from the sign-in page couldn't be used.",
    },
  },
} as const;

export type SignInError = keyof typeof COPY.error.reasons;

export function isSignInError(code: unknown): code is SignInError {
  return typeof code === "string" && code in COPY.error.reasons;
}
