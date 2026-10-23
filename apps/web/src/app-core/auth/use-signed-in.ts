import { useEffect, useState } from "react";
import { accessToken, currentRoute, ensureSession, signIn } from "./session";

/**
 * Whether this page has a session, refreshing one from the BFF cookie on a fresh load (P-01-T11).
 * With none, it starts sign-in and comes back to `returnTo` (the current route by default), so an
 * expired session lands where the person was (AC 5.1.4).
 */
export function useSignedIn(returnTo?: string, options: { enabled?: boolean } = {}): boolean {
  const enabled = options.enabled ?? true;
  const [signedIn, setSignedIn] = useState(() => accessToken() !== null);
  useEffect(() => {
    if (signedIn || !enabled) return undefined;
    let live = true;
    void ensureSession().then((ok) => {
      if (!live) return;
      if (ok) setSignedIn(true);
      else signIn(returnTo ?? currentRoute());
    });
    return () => {
      live = false;
    };
  }, [signedIn, enabled, returnTo]);
  return signedIn;
}
