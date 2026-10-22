import { listEngagementsOptions, meOptions, yourPartOptions } from "@abacus/api-client/query";
import type { EngagementSummaryOut, YourPartOut } from "@abacus/api-client";
import { Alert, Button, Card, EmptyState, Spinner, StatusPill } from "@abacus/ui";
import { useQueries, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type JSX, useEffect, useState } from "react";
import { errorMessage } from "../api";
import { PortalBrand } from "../shell/PortalBrand";
import { accessToken, chooseTenant, signIn, signOut } from "../auth/session";
import { yourPartMessage } from "./clientHubMessages";

/** The client portal (ADR-011's separate tree; SPEC-016): the firms the client works with. */
export function ClientHome(): JSX.Element {
  const signedIn = accessToken() !== null;
  useEffect(() => {
    if (!signedIn) void signIn("/client");
  }, [signedIn]);
  const me = useQuery({ ...meOptions(), enabled: signedIn });
  return (
    <div className="min-h-screen bg-ground">
      <header className="flex h-[46px] items-center justify-between border-b-[0.5px] border-hair bg-card px-4">
        <PortalBrand />
        <span className="flex items-center gap-2">
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
        </span>
      </header>
      <main className="mx-auto flex max-w-3xl flex-col gap-4 p-6">
        {!signedIn || me.isPending ? (
          <Spinner label="Loading…" />
        ) : me.isError ? (
          <Alert title="Couldn't load your account">{errorMessage(me.error)}</Alert>
        ) : (
          <>
            <h1 className="px-1 text-[20px] font-medium tracking-[-0.015em]">
              Welcome, {me.data.display_name}
            </h1>
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
                      <Card className="flex flex-col gap-2 p-0">
                        <h2 className="border-b-[0.5px] border-hair px-4 py-3 text-[14.5px] font-medium">
                          {m.firm_name}
                        </h2>
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
              <Link to="/" className="text-body text-accent hover:underline">
                Go to your firm workspace
              </Link>
            )}
          </>
        )}
      </main>
    </div>
  );
}

/** SPEC-020 AC-1, SPEC-031 AC-6 (TASK-099): the engagements this client works on with the chosen
 * firm, the ones that need them first, each with what's left; finished ones fold away. */
function ClientEngagements(): JSX.Element {
  const engagements = useQuery(listEngagementsOptions());
  const list = engagements.data ?? [];
  const parts = useQueries({
    queries: list.map((e) => ({
      ...yourPartOptions({ path: { engagement_id: e.id } }),
      retry: false,
    })),
  });
  const [showDone, setShowDone] = useState(false);
  if (engagements.isPending) return <Spinner label="Loading engagements…" />;
  if (engagements.isError) {
    return <Alert title="Couldn't load engagements">{errorMessage(engagements.error)}</Alert>;
  }
  if (list.length === 0) {
    return (
      <p className="px-4 pb-4 text-[13px] text-ink-2">
        Your auditor will share what they need from you here.
      </p>
    );
  }
  const rows = list.map((e, i) => ({ e, part: parts[i]?.data }));
  const open = rows
    .filter((r) => r.part === undefined || r.part.items_left > 0)
    .sort(
      (a, b) =>
        (b.part?.blocks_fieldwork ?? 0) - (a.part?.blocks_fieldwork ?? 0) ||
        (b.part?.items_left ?? 0) - (a.part?.items_left ?? 0),
    );
  const done = rows.filter((r) => r.part !== undefined && r.part.items_left === 0);
  return (
    <div className="flex flex-col pb-2">
      {open.length === 0 && (
        <p className="px-4 py-2 text-[13px] text-ink-2">Nothing needs you right now.</p>
      )}
      <ul className="flex flex-col divide-y-[0.5px] divide-hair">
        {open.map((r) => (
          <EngagementRow key={r.e.id} engagement={r.e} part={r.part} />
        ))}
      </ul>
      {done.length > 0 && (
        <>
          <button
            type="button"
            aria-expanded={showDone}
            onClick={() => {
              setShowDone((v) => !v);
            }}
            className="mx-2 mt-1 flex h-[30px] items-center rounded-tile px-2 text-left text-[12.5px] text-ink-2 hover:bg-nav-fill hover:text-ink"
          >
            {showDone ? "Hide" : "Show"} {done.length} with nothing left for you
          </button>
          {showDone && (
            <ul className="flex flex-col divide-y-[0.5px] divide-hair">
              {done.map((r) => (
                <EngagementRow key={r.e.id} engagement={r.e} part={r.part} />
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

function EngagementRow({
  engagement: e,
  part,
}: {
  engagement: EngagementSummaryOut;
  part: YourPartOut | undefined;
}): JSX.Element {
  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2.5">
      <div className="flex min-w-0 flex-1 flex-col">
        <Link
          to="/client/engagements/$engagementId"
          params={{ engagementId: e.id }}
          className="text-[13px] font-medium text-ink hover:underline"
        >
          {e.name}
        </Link>
        <span className="text-[12px] text-ink-3 tabular-nums">
          {e.fiscal_period_start} to {e.fiscal_period_end}
        </span>
      </div>
      {part !== undefined && (
        <StatusPill
          tone={
            part.items_left === 0 ? "success" : part.blocks_fieldwork > 0 ? "danger" : "warning"
          }
        >
          <span aria-label="Your part">{yourPartMessage(part)}</span>
        </StatusPill>
      )}
    </li>
  );
}
