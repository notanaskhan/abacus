import { engagementGraphOptions } from "@abacus/api-client/query";
import { Alert, Button, EmptyState, Panel, Skeleton, StatusPill } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { errorMessage } from "../api";
import { balance, statusOf } from "./engagementLabels";

/** SPEC-016 AC-4: gaps first, then each area's accounts beside its requests. */
export function MapView({ engagementId }: { engagementId: string }): JSX.Element {
  const graph = useQuery(engagementGraphOptions({ path: { engagement_id: engagementId } }));
  if (graph.isPending) return <Skeleton className="h-64" />;
  if (graph.isError) {
    return (
      <Alert
        title="Couldn't load the map"
        action={
          <Button size="sm" variant="outline" onClick={() => void graph.refetch()}>
            Retry
          </Button>
        }
      >
        {errorMessage(graph.error)}
      </Alert>
    );
  }
  const g = graph.data;
  const noRequests = g.gaps.areas_with_accounts_without_requests;
  const hasGaps = g.gaps.unmapped_accounts.length > 0 || noRequests.length > 0;
  return (
    <div className="flex flex-col gap-4">
      {g.snapshot_id === null && (
        <EmptyState title="No ledger snapshot yet">
          Accounts appear once a trial balance is retrieved or uploaded.
        </EmptyState>
      )}
      {hasGaps && (
        <Panel title="Gaps" className="border-warn/40 bg-warn-soft">
          {g.gaps.unmapped_accounts.length > 0 && (
            <div className="flex flex-col gap-1">
              <h3 className="font-sans text-sm font-semibold">Accounts no area covers</h3>
              <AccountList accounts={g.gaps.unmapped_accounts} />
            </div>
          )}
          {noRequests.length > 0 && (
            <p className="text-sm">
              <span className="font-semibold">Areas with accounts but no requests: </span>
              {noRequests.join(", ")}
            </p>
          )}
        </Panel>
      )}
      {g.areas.map((area) => (
        <Panel
          key={area.name}
          title={area.name}
          action={
            area.items.length === 0 ? (
              <StatusPill tone="warning">No requests</StatusPill>
            ) : undefined
          }
        >
          <div className="grid gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-1">
              <h3 className="font-sans text-xs font-semibold tracking-wide text-muted uppercase">
                Accounts
              </h3>
              {area.accounts.length === 0 ? (
                <p className="text-sm text-muted">None mapped</p>
              ) : (
                <AccountList accounts={area.accounts} />
              )}
            </div>
            <div className="flex flex-col gap-1">
              <h3 className="font-sans text-xs font-semibold tracking-wide text-muted uppercase">
                Requests
              </h3>
              {area.items.length === 0 ? (
                <p className="text-sm text-muted">None</p>
              ) : (
                <ul className="flex flex-col gap-1 text-sm">
                  {area.items.map((item) => {
                    const status = statusOf(item.status);
                    return (
                      <li key={item.id} className="flex items-center justify-between gap-2">
                        <span>{item.description}</span>
                        <StatusPill tone={status.tone}>{status.label}</StatusPill>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>
        </Panel>
      ))}
    </div>
  );
}

function AccountList({
  accounts,
}: {
  accounts: { code: string; name: string; balance: string }[];
}): JSX.Element {
  return (
    <ul className="flex flex-col text-sm">
      {accounts.map((a) => (
        <li
          key={a.code}
          className="flex items-baseline gap-3 border-b border-line py-1 last:border-b-0"
        >
          <span className="w-16 text-muted tabular-nums">{a.code}</span>
          <span className="flex-1">{a.name}</span>
          <span className="tabular-nums">{balance(a.balance)}</span>
        </li>
      ))}
    </ul>
  );
}
