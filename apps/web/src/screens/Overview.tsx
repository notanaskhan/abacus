import type { GraphAreaOut } from "@abacus/api-client";
import {
  applyMethodologyMutation,
  getEngagementOptions,
  engagementGraphOptions,
  engagementGraphQueryKey,
  listTemplatesOptions,
} from "@abacus/api-client/query";
import {
  AiTag,
  Alert,
  Button,
  Count,
  EmptyState,
  Panel,
  Skeleton,
  StatusPill,
  Table,
  Td,
  Th,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { SCREENING, statusOf } from "./engagementLabels";
import { ConnectionPanel } from "./ConnectionPanel";

/** SPEC-016 AC-3: areas with progress, the selected area's requests, gaps and screening. */
export function Overview({ engagementId }: { engagementId: string }): JSX.Element {
  const graph = useQuery(engagementGraphOptions({ path: { engagement_id: engagementId } }));
  const [selected, setSelected] = useState<string | null>(null);

  if (graph.isPending) {
    return (
      <div className="flex flex-col gap-2" aria-busy="true">
        <Skeleton className="h-10" />
        <Skeleton className="h-64" />
      </div>
    );
  }
  if (graph.isError) {
    return (
      <Alert
        title="Couldn't load the engagement"
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
  const items = g.areas.flatMap((a) => a.items);
  const done = (area: GraphAreaOut): number =>
    area.items.filter((i) => i.status !== "open").length;
  const area = g.areas.find((a) => a.name === selected) ?? g.areas[0];
  const ready = items.filter((i) => i.screening_action === "ready_for_review").length;
  const revise = items.filter((i) => i.screening_action === "needs_revision").length;
  const unscreened = items.filter(
    (i) => i.evidence_version_id !== null && i.screening_action === null,
  ).length;

  return (
    <div className="flex flex-col gap-4">
      {g.methodology === null && <ApplyMethodology engagementId={engagementId} />}
      <ConnectionPanel engagementId={engagementId} firmName="" canConnect={false} />
      <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)_300px]">
        <Panel
          title="Audit areas"
          action={
            <Count
              done={items.filter((i) => i.status !== "open").length}
              total={items.length}
              label="received"
            />
          }
        >
          {g.areas.length === 0 ? (
            <p className="text-sm text-muted">
              No areas yet. Apply a methodology or add request items.
            </p>
          ) : (
            <ul className="flex flex-col gap-0.5">
              {g.areas.map((a) => {
                const current = a.name === area?.name;
                const gap = a.items.length === 0;
                return (
                  <li key={a.name}>
                    <button
                      type="button"
                      aria-pressed={current}
                      onClick={() => {
                        setSelected(a.name);
                      }}
                      className={`flex w-full items-center gap-2 rounded-[var(--radius-control)] px-2.5 py-2 text-left text-sm hover:bg-sunken ${current ? "bg-accent-soft font-semibold" : ""}`}
                    >
                      <span className="flex-1">{a.name}</span>
                      {gap && <StatusPill tone="warning">No requests</StatusPill>}
                      <Count done={done(a)} total={a.items.length} />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <section aria-labelledby="area-heading" className="flex min-w-0 flex-col gap-3">
          <div className="flex flex-wrap items-baseline gap-3">
            <h2 id="area-heading" className="text-2xl">
              {area?.name ?? "Requests"}
            </h2>
            {area !== undefined && (
              <Count
                done={done(area)}
                total={area.items.length}
                label={`received · ${String(area.accounts.length)} accounts`}
              />
            )}
          </div>
          {area === undefined || area.items.length === 0 ? (
            <EmptyState title="No requests in this area">
              Add request items from the Requests tab, or check the map for accounts that need
              them.
            </EmptyState>
          ) : (
            <div className="overflow-x-auto rounded-[var(--radius-panel)] border border-line bg-surface">
              <Table className="min-w-[640px]">
                <thead>
                  <tr>
                    <Th>Request</Th>
                    <Th>Tier</Th>
                    <Th>Status</Th>
                    <Th>Evidence</Th>
                    <Th>Screening</Th>
                  </tr>
                </thead>
                <tbody>
                  {area.items.map((item) => {
                    const status = statusOf(item.status);
                    return (
                      <tr key={item.id}>
                        <Td className="font-semibold">{item.description}</Td>
                        <Td className="text-muted">{item.retrievability_tier ?? "—"}</Td>
                        <Td>
                          <StatusPill tone={status.tone}>{status.label}</StatusPill>
                        </Td>
                        <Td className="text-muted">
                          {item.evidence_version_id === null ? "—" : "Received"}
                        </Td>
                        <Td>
                          {item.screening_action === null ? (
                            <span className="text-muted">—</span>
                          ) : (
                            <span className="inline-flex items-center gap-2">
                              <AiTag />
                              {SCREENING[item.screening_action] ?? item.screening_action}
                            </span>
                          )}
                        </Td>
                      </tr>
                    );
                  })}
                </tbody>
              </Table>
            </div>
          )}
        </section>

        <div className="flex flex-col gap-4">
          <Panel title="Coverage gaps">
            <ul className="flex flex-col gap-2 text-sm">
              <GapRow
                label="Unmapped accounts with balances"
                count={g.gaps.unmapped_accounts.length}
                engagementId={engagementId}
              />
              <GapRow
                label="Areas with accounts but no requests"
                count={g.gaps.areas_with_accounts_without_requests.length}
                engagementId={engagementId}
              />
              <GapRow
                label="Requests with no evidence"
                count={g.gaps.items_without_evidence.length}
                engagementId={engagementId}
              />
            </ul>
          </Panel>
          <Panel title="Screening">
            <p className="text-sm text-muted">Proposals only. A reviewer decides each item.</p>
            <dl className="grid grid-cols-3 gap-2 text-sm">
              <div className="rounded-[var(--radius-control)] bg-ok-soft p-2.5 text-ok">
                <dt className="text-xs">Ready for review</dt>
                <dd className="text-xl font-semibold tabular-nums">{ready}</dd>
              </div>
              <div className="rounded-[var(--radius-control)] bg-warn-soft p-2.5 text-warn">
                <dt className="text-xs">Needs revision</dt>
                <dd className="text-xl font-semibold tabular-nums">{revise}</dd>
              </div>
              <div className="rounded-[var(--radius-control)] bg-sunken p-2.5">
                <dt className="text-xs">Not screened</dt>
                <dd className="text-xl font-semibold tabular-nums">{unscreened}</dd>
              </div>
            </dl>
          </Panel>
          <Panel title="People">
            <p className="text-sm text-muted">
              Team:{" "}
              {g.team.length === 0 ? "nobody yet" : g.team.map((m) => m.display_name).join(", ")}
            </p>
            <Link
              to="/engagements/$engagementId/people"
              params={{ engagementId }}
              className="text-sm text-accent hover:underline"
            >
              Manage people
            </Link>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function GapRow({
  label,
  count,
  engagementId,
}: {
  label: string;
  count: number;
  engagementId: string;
}): JSX.Element {
  return (
    <li className="flex items-center justify-between gap-2 rounded-[var(--radius-control)] border border-line p-2.5">
      <span>{label}</span>
      <Link
        to="/engagements/$engagementId/map"
        params={{ engagementId }}
        className="font-semibold text-accent tabular-nums hover:underline"
      >
        {count}
      </Link>
    </li>
  );
}

/** With no methodology pinned: pick a version and seed the request list (SPEC-008 AC-4). */
export function ApplyMethodology({ engagementId }: { engagementId: string }): JSX.Element {
  const queryClient = useQueryClient();
  const templates = useQuery(listTemplatesOptions());
  const engagement = useQuery(getEngagementOptions({ path: { engagement_id: engagementId } }));
  const [version, setVersion] = useState("");
  const apply = useMutation({
    ...applyMethodologyMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: engagementGraphQueryKey({ path: { engagement_id: engagementId } }),
      });
    },
  });
  // SPEC-024 AC-6: only templates for this engagement's type.
  const type = engagement.data?.type ?? "audit";
  const offered = (templates.data ?? []).filter((t) => t.engagement_types?.includes(type));
  if (templates.isError || offered.length === 0) return <></>;
  return (
    <Panel title="Start from your methodology">
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (version !== "")
            apply.mutate({ path: { engagement_id: engagementId }, body: { version_id: version } });
        }}
      >
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Methodology version
          <select
            value={version}
            onChange={(event) => {
              setVersion(event.target.value);
            }}
            className="h-9 rounded-[var(--radius-control)] border border-line bg-surface px-3 font-normal"
          >
            <option value="">Choose a version…</option>
            {offered.map((t) => (
              <option key={t.version_id} value={t.version_id}>
                {t.template_name} · v{t.version}
              </option>
            ))}
          </select>
        </label>
        <Button type="submit" disabled={version === "" || apply.isPending}>
          Apply and create requests
        </Button>
        {apply.isError && (
          <p role="alert" className="text-sm text-danger">
            {errorMessage(apply.error)}
          </p>
        )}
      </form>
    </Panel>
  );
}
