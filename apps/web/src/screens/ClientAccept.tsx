import { acceptInvitationMutation, meQueryKey } from "@abacus/api-client/query";
import { Card, Spinner } from "@abacus/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { type JSX, type ReactNode, useEffect, useRef } from "react";
import { accessToken, signIn } from "../auth/session";

const TOKEN_KEY = "abacus.invitation";
export const ACCEPT_PATH = "/client/accept";

/** Moves `#token=…` out of the address bar into this tab's storage until it is used (AC-7). */
export function takeTokenFromFragment(): void {
  const match = /(?:^#|&)token=([\w-]{20,200})/.exec(window.location.hash);
  if (match?.[1] !== undefined) {
    sessionStorage.setItem(TOKEN_KEY, match[1]);
    window.history.replaceState(null, "", window.location.pathname);
  }
}

function useToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

/** SPEC-016 AC-7: open the emailed link, sign in passwordlessly, accept, land on the client home. */
export function Accept(): JSX.Element {
  takeTokenFromFragment();
  const token = useToken();
  const signedIn = accessToken() !== null;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const started = useRef(false);
  const accept = useMutation({
    ...acceptInvitationMutation(),
    onSettled: () => {
      sessionStorage.removeItem(TOKEN_KEY); // used once, whatever happened
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: meQueryKey() });
      void navigate({ to: "/client" });
    },
  });

  useEffect(() => {
    if (token === null || started.current) return;
    if (!signedIn) {
      void signIn(ACCEPT_PATH);
      return;
    }
    started.current = true;
    accept.mutate({ body: { token } });
  }, [token, signedIn, accept]);

  if (accept.isError || (token === null && !accept.isPending && !accept.isSuccess)) {
    return (
      <Shell>
        <h1 className="text-2xl">This invitation can&apos;t be used</h1>
        <p className="text-sm text-muted">
          The link may have expired, been used already, or been sent to a different email address.
          Ask your auditor to send a new invitation.
        </p>
      </Shell>
    );
  }
  return (
    <Shell>
      <h1 className="text-2xl">Joining your engagement</h1>
      <Spinner label={signedIn ? "Accepting your invitation…" : "Taking you to sign in…"} />
    </Shell>
  );
}

function Shell({ children }: { children: ReactNode }): JSX.Element {
  return (
    <main className="flex min-h-screen items-center justify-center bg-ground p-6">
      <Card className="flex w-full max-w-md flex-col gap-3 p-6">
        <p className="font-display text-lg font-semibold">Abacus</p>
        {children}
      </Card>
    </main>
  );
}
