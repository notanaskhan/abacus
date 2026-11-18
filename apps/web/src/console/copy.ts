// The console entry's own words (G-04-T14). The handoff draws no console sign-in frame (PLT-01's
// spec names none), so the gate borrows SHL-06's title, its retry action word and its refusal
// sentences; the one console-only refusal (no console role) and the frame's title are recorded with
// DEC-5528 and DEC-5532 as undesigned.
import { COPY as SHL06 } from "../screens/SHL-06/copy";
import { COPY as PLT01 } from "../screens/PLT-01/copy";

export const CONSOLE_COPY = {
  title: PLT01.console,
  signIn: { title: SHL06.title, action: "Sign in" },
  signOut: "Sign out",
  refusals: {
    mfa_required_at_sign_in: SHL06.error.reasons.mfa_required_at_sign_in,
    sign_in_failed: SHL06.error.reasons.sign_in_failed,
    session_expired: SHL06.error.reasons.session_expired,
    session_refresh_reused: SHL06.error.reasons.session_refresh_reused,
    no_console_role: "This staff account has no console role. Ask an Accrued platform admin.",
  } as Record<string, string>,
} as const;
