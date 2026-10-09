import { listEngagementsOptions, meOptions } from "@abacus/api-client/query";
import { Alert, Button, Card, EmptyState, Spinner } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type JSX, useEffect } from "react";
import { errorMessage } from "../api";
import { accessToken, chooseTenant, signIn, signOut } from "../auth/session";

/** The client portal (ADR-011's separate tree; SPEC-016): the firms the client works with. */
export function ClientHome(): JSX.Element {
  const signedIn = accessToken() !== null;
  useEffect(() => {
    if (!signedIn) void signIn("/client");
  }, [signedIn]);
  const me = useQuery({ ...meOptions(), enabled: signedIn });
  return (
    <div className="min-h-screen bg-ground">
      <header className="flex items-center justify-between border-b border-line bg-surface px-6 py-3">
        <span className="font-display text-lg font-semibold">Abacus</span>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            signOut();
            void signIn("/client");
          }}
        >
          Sign out
        </Button>
      </header>
      <main className="mx-auto flex max-w-3xl flex-col gap-4 p-6">
        {!signedIn || me.isPending ? (
          <Spinner label="Loading…" />
        ) : me.isError ? (
          <Alert title="Couldn't load your account">{errorMessage(me.error)}</Alert>
        ) : (
          <>
            <h1 className="text-3xl">Welcome, {me.data.display_name}</h1>
            {me.data.memberships.filter((m) => m.kind === "client").length === 0 ? (
              <EmptyState title="You haven't joined an engagement yet">
                Open the invitation link your auditor emailed you.
              </EmptyState>
            ) : (
              <ul className="flex flex-col gap-3">
                {me.data.memberships
                  .filter((m) => m.kind === "client")
                  .map((m) => (
                    <li key={m.tenant_id}>
                      <Card className="flex flex-col gap-1">
                        <h2 className="text-xl">{m.firm_name}</h2>
                        {me.data.active_tenant_id === m.tenant_id ? (
                          <ClientEngagements />
                        ) : (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="self-start"
                            onClick={() => {
                              chooseTenant(m.tenant_id);
                            }}
                          >
                            Use this firm
                          </Button>
                        )}
                      </Card>
                    </li>
                  ))}
              </ul>
            )}
            {me.data.memberships.some((m) => m.kind === "staff") && (
              <Link to="/" className="text-sm text-accent hover:underline">
                Go to your firm workspace
              </Link>
            )}
          </>
        )}
      </main>
    </div>
  );
}

/** SPEC-020 AC-1: the engagements this client works on with the chosen firm. */
function ClientEngagements(): JSX.Element {
  const engagements = useQuery(listEngagementsOptions());
  if (engagements.isPending) return <Spinner label="Loading engagements…" />;
  if (engagements.isError) {
    return <Alert title="Couldn't load engagements">{errorMessage(engagements.error)}</Alert>;
  }
  if (engagements.data.length === 0) {
    return (
      <p className="text-sm text-muted">Your auditor will share what they need from you here.</p>
    );
  }
  return (
    <ul className="flex flex-col gap-1">
      {engagements.data.map((e) => (
        <li key={e.id}>
          <Link
            to="/client/engagements/$engagementId"
            params={{ engagementId: e.id }}
            className="text-accent hover:underline"
          >
            {e.name}
          </Link>{" "}
          <span className="text-sm text-muted tabular-nums">
            {e.fiscal_period_start} to {e.fiscal_period_end}
          </span>
        </li>
      ))}
    </ul>
  );
}
