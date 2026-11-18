// The console's staff sign-in gate (G-04-T14; SPEC-680 P-54; DEC-5528). Platform staff sign in on
// the staff issuer with staff MFA, never as firm members (ADR-028). The sign-in is a top-level
// navigation to the console BFF (`GET /v1/platform/auth/sign-in?return_to=`), the same shape as the
// firm's (ADR-165): the BFF holds the session in a `__Host-` cookie, so the page keeps no token in
// web storage and the CSP's `connect-src 'self'` holds. The BFF itself is the follow-up red identity
// task recorded with DEC-5528; until it lands the gate shows the sign-in frame and nothing else.
// In fixture mode the PLT-01 persona (Rowan Achebe) is signed in.
import { Button } from "@abacus/ui";
import type { JSX, ReactNode } from "react";
import { CONSOLE_COPY as C } from "./copy";

export const STAFF_SIGN_IN_PATH = "/v1/platform/auth/sign-in";

/** The console BFF's sign-in URL with a same-origin return path (never another origin). */
export function staffSignInUrl(returnTo: string): string {
  const safe = returnTo.startsWith("/") && !returnTo.startsWith("//") ? returnTo : "/";
  return `${STAFF_SIGN_IN_PATH}?${new URLSearchParams({ return_to: safe }).toString()}`;
}

export function StaffAuth({
  signedIn,
  children,
  navigate = (url) => {
    window.location.assign(url);
  },
}: {
  signedIn: boolean;
  children: ReactNode;
  navigate?: (url: string) => void;
}): JSX.Element {
  if (signedIn) return <>{children}</>;
  return (
    <main
      data-console="sign-in"
      className="flex min-h-screen flex-col items-center justify-center gap-[12px] bg-shell"
    >
      <h1 className="text-pane font-medium text-ink">{C.signIn.title}</h1>
      <Button
        variant="primary"
        onClick={() => {
          navigate(staffSignInUrl(window.location.pathname + window.location.search));
        }}
      >
        {C.signIn.action}
      </Button>
    </main>
  );
}
