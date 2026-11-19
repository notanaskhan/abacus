// The console shell (G-04-T14; G-04 §5.1, §5.3; DEC-5528, DEC-5532): the staff sign-in gate around
// PLT-01. In fixture mode (`VITE_FIXTURES=1`, `?st=a…g`) the Rowan Achebe persona is signed in and
// PLT-01 renders its artboards; Library releases (e) shows only there. A production build folds the
// fixture flag to a constant, so the seed-backed PLT-01 screen and the seed are dropped from
// dist/console (scripts/console-dist-check.mjs holds it). There, the shell asks the console BFF for
// a session (console/auth.ts): `/signin/callback?to=` finishes a sign-in and lands on its path,
// `?error=` shows the gate with the refusal; signed in, the console frame shows G-04-T17's sections
// (Support sessions, Status, Publications, the Support queue and Plan requests) on the live API.
import { Button, Skeleton } from "@abacus/ui";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type JSX, Suspense, lazy, useEffect, useState } from "react";
import { refreshConsoleSession, signOutConsole } from "./auth";
import { CONSOLE_COPY as C } from "./copy";
import { LiveSections } from "./sections/live";
import { StaffAuth } from "./StaffAuth";

const queryClient = new QueryClient();

const FIXTURES = import.meta.env.VITE_FIXTURES === "1";

const FixtureConsole = FIXTURES
  ? lazy(async () => ({ default: (await import("../screens/PLT-01")).TenantConsole }))
  : null;

type Session = "checking" | "signed_in" | "signed_out";

/** The callback landing's facts: where to go next, or why sign-in was refused. */
export function callbackOf(
  pathname: string,
  search: string,
): { to?: string; error?: string } | null {
  if (pathname !== "/signin/callback") return null;
  const params = new URLSearchParams(search);
  const error = params.get("error");
  if (error !== null) return { error };
  const to = params.get("to");
  return { to: to !== null && to.startsWith("/") && !to.startsWith("//") ? to : "/" };
}

function LiveConsole(): JSX.Element {
  const [session, setSession] = useState<Session>("checking");
  const [refusal, setRefusal] = useState<string | null>(null);
  useEffect(() => {
    const landing = callbackOf(window.location.pathname, window.location.search);
    if (landing?.error !== undefined) {
      setRefusal(landing.error);
      setSession("signed_out");
      return;
    }
    void refreshConsoleSession(undefined, { active: true }).then((ok) => {
      if (ok && landing?.to !== undefined) window.history.replaceState(null, "", landing.to);
      setSession(ok ? "signed_in" : "signed_out");
    });
  }, []);
  if (session === "checking") return <Skeleton className="m-[12px] h-[480px]" />;
  return (
    <StaffAuth signedIn={session === "signed_in"} refusal={refusal}>
      <main
        data-console="signed-in"
        className="flex min-h-screen flex-col gap-[12px] bg-shell p-[12px]"
      >
        <header className="flex h-[46px] items-center justify-between">
          <h1 className="text-pane font-medium text-ink">{C.title}</h1>
          <Button
            variant="secondary"
            onClick={() => {
              void signOutConsole().then(() => {
                setSession("signed_out");
              });
            }}
          >
            {C.signOut}
          </Button>
        </header>
        {session === "signed_in" ? (
          <QueryClientProvider client={queryClient}>
            <LiveSections />
          </QueryClientProvider>
        ) : null}
      </main>
    </StaffAuth>
  );
}

export function ConsoleShell({ search }: { search: string }): JSX.Element {
  if (FixtureConsole === null) return <LiveConsole />;
  const st = new URLSearchParams(search).get("st") ?? undefined;
  return (
    <StaffAuth signedIn>
      <Suspense fallback={<Skeleton className="h-[480px]" />}>
        <FixtureConsole st={st} />
      </Suspense>
    </StaffAuth>
  );
}
