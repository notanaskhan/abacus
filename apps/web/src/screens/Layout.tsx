import { meOptions } from "@abacus/api-client/query";
import { Alert, Button, Card, Spinner } from "@abacus/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Outlet } from "@tanstack/react-router";
import { type JSX, useEffect, useState } from "react";
import { App } from "../App";
import { errorMessage } from "../api";
import { accessToken, chooseTenant, chosenTenant, signIn, signOut } from "../auth/session";

/** Signed-in shell: who you are, in which firm (SPEC-000 AC-1), and the page. */
export function Layout(): JSX.Element {
  const signedIn = accessToken() !== null;
  useEffect(() => {
    if (!signedIn) void signIn();
  }, [signedIn]);
  if (!signedIn) {
    return <App status="Redirecting to sign-in…" />;
  }
  return <SignedIn />;
}

function SignedIn(): JSX.Element {
  const queryClient = useQueryClient();
  const me = useQuery(meOptions());
  // React state, so choosing a firm re-renders (the API reports no active firm for users in
  // several; the choice is also kept for the client's X-Abacus-Tenant header).
  const [picked, setPicked] = useState<string | null>(chosenTenant);

  if (me.isPending) {
    return (
      <main className="p-8">
        <Spinner label="Loading your account…" />
      </main>
    );
  }
  if (me.isError) {
    return (
      <main className="mx-auto max-w-md p-8">
        <Alert
          title="Couldn't load your account"
          action={
            <Button size="sm" variant="outline" onClick={() => void me.refetch()}>
              Retry
            </Button>
          }
        >
          {errorMessage(me.error)}
        </Alert>
      </main>
    );
  }

  const tenant = me.data.active_tenant_id ?? picked;
  const firm = me.data.memberships.find((m) => m.tenant_id === tenant);
  if (firm === undefined) {
    return (
      <main className="mx-auto max-w-md p-8">
        <Card>
          <h1 className="mb-3 text-lg font-semibold">Choose a firm</h1>
          <ul className="flex flex-col gap-2">
            {me.data.memberships.map((m) => (
              <li key={m.tenant_id}>
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => {
                    chooseTenant(m.tenant_id);
                    setPicked(m.tenant_id);
                    void queryClient.invalidateQueries();
                  }}
                >
                  {m.firm_name}
                </Button>
              </li>
            ))}
          </ul>
        </Card>
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="flex items-center justify-between border-b border-neutral-200 bg-white px-6 py-3">
        <Link to="/" className="font-semibold">
          Abacus
        </Link>
        <div className="flex items-center gap-3 text-sm">
          <span>
            {me.data.display_name} · {firm.firm_name}
          </span>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              signOut();
              queryClient.clear();
              void signIn("/");
            }}
          >
            Sign out
          </Button>
        </div>
      </header>
      <main className="mx-auto max-w-5xl p-6">
        <Outlet />
      </main>
    </div>
  );
}
