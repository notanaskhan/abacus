import type { ItemVersionOut, ScreeningResultOut } from "@abacus/api-client";
import { content } from "@abacus/api-client";
import {
  getEngagementOptions,
  itemVersionsOptions,
  itemVersionsQueryKey,
  listRequestItemsOptions,
  listRequestItemsQueryKey,
  listScreeningResultsOptions,
  meOptions,
  reviewQueueQueryKey,
} from "@abacus/api-client/query";
import {
  AgentText,
  AiTag,
  Alert,
  Badge,
  Button,
  EmptyState,
  Panel,
  Skeleton,
  StatusPill,
} from "@abacus/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { confidencePercent } from "../board/join";
import { isForbidden } from "../shell/mfa";
import { DecisionActions } from "./DecisionActions";
import { statusOf } from "./engagementLabels";

const DECIDERS = new Set(["engagement_partner", "manager", "senior"]);
const DECISION_LABEL: Record<string, string> = {
  accept: "Accepted",
  reject: "Rejected",
  send_back: "Sent back",
};
const ACTION_LABEL: Record<string, string> = {
  ready_for_review: "Looks ready for review",
  needs_revision: "Needs revision",
};
const NOT_VERIFIED: Record<string, string> = {
  cell_not_found: "the cited cell doesn't exist",
  value_mismatch: "the value doesn't match the cell",
  quote_mismatch: "the quote doesn't match the cell",
};

function size(bytes: number): string {
  if (bytes < 1024) return `${String(bytes)} B`;
  return bytes < 1024 * 1024
    ? `${String(Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function when(value: string | null): string {
  return value === null ? "—" : new Date(value).toLocaleString();
}

/** SPEC-021: one request item with every evidence version, its screening and the decision. */
export function ItemDetail({
  engagementId,
  itemId,
}: {
  engagementId: string;
  itemId: string;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const items = useQuery(listRequestItemsOptions(path));
  const versions = useQuery({
    ...itemVersionsOptions({ path: { engagement_id: engagementId, item_id: itemId } }),
    retry: false,
  });
  const screening = useQuery(listScreeningResultsOptions(path));
  const engagement = useQuery(getEngagementOptions(path));
  const me = useQuery(meOptions());
  const [selected, setSelected] = useState<string | null>(null);

  const item = items.data?.find((i) => i.id === itemId);
  const team = engagement.data?.team ?? [];
  const myRole = team.find((m) => m.user_id === me.data?.user_id)?.role;
  const assignee = item?.client_assignee_user_id ?? null;

  if (versions.isError && isForbidden(versions.error)) {
    return <Alert title="Not allowed">You can't see this request's evidence.</Alert>;
  }
  if (items.isPending) return <Skeleton className="h-40" />;
  if (items.isError) {
    return <Alert title="Couldn't load the request">{errorMessage(items.error)}</Alert>;
  }
  if (item === undefined) {
    return <Alert title="Request not found">It may have been removed from this engagement.</Alert>;
  }

  const list = versions.data ?? [];
  const newest = list[0];
  const shown = list.find((v) => v.id === selected) ?? newest;
  const resultFor = (versionId: string): ScreeningResultOut | undefined =>
    (screening.data ?? [])
      .filter((r) => r.evidence_version_id === versionId)
      .sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  const status = statusOf(item.status);
  const refresh = (): void => {
    void queryClient.invalidateQueries({
      queryKey: itemVersionsQueryKey({
        path: { engagement_id: engagementId, item_id: itemId },
      }),
    });
    void queryClient.invalidateQueries({ queryKey: listRequestItemsQueryKey(path) });
    void queryClient.invalidateQueries({ queryKey: reviewQueueQueryKey(path) });
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl whitespace-pre-line">{item.description}</h2>
          <p className="text-sm text-muted">
            {item.audit_area}
            {item.retrievability_tier != null && ` · Tier ${item.retrievability_tier}`}
            {item.client_visible === false && " · Hidden from client"}
            {assignee !== null && ` · Assigned to a client contributor`}
          </p>
        </div>
        <StatusPill tone={status.tone}>{status.label}</StatusPill>
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel title="Evidence">
          {versions.isPending ? (
            <Skeleton className="h-24" />
          ) : versions.isError ? (
            <Alert title="Couldn't load the evidence">{errorMessage(versions.error)}</Alert>
          ) : list.length === 0 ? (
            <EmptyState title="No evidence yet">
              Retrieve it from the client's ledger on the Requests board, or wait for the client to
              upload it.
            </EmptyState>
          ) : (
            <ol aria-label="Evidence versions" className="flex flex-col gap-2">
              {list.map((v) => (
                <li key={v.id}>
                  <VersionCard
                    engagementId={engagementId}
                    version={v}
                    selected={v.id === shown?.id}
                    onSelect={() => {
                      setSelected(v.id);
                    }}
                  />
                </li>
              ))}
            </ol>
          )}
        </Panel>
        {shown !== undefined && (
          <div className="flex flex-col gap-4">
            <Screening result={resultFor(shown.id)} loading={screening.isPending} />
            <Panel title="Decision">
              {shown.decision !== null ? (
                <p className="text-sm">
                  <Badge tone={shown.decision.decision === "accept" ? "success" : "warning"}>
                    {DECISION_LABEL[shown.decision.decision] ?? shown.decision.decision}
                  </Badge>{" "}
                  {shown.decision.reason_code !== null && `(${shown.decision.reason_code}) `}
                  by {shown.decision.decided_by_name || "a reviewer"} on{" "}
                  {when(shown.decision.decided_at)}
                </p>
              ) : shown.id !== newest?.id ? (
                <p className="text-sm text-muted">A newer version replaced this one.</p>
              ) : myRole !== undefined && DECIDERS.has(myRole) ? (
                <DecisionActions
                  engagementId={engagementId}
                  versionId={shown.id}
                  itemLabel={item.description}
                  seenProposal={resultFor(shown.id)?.id ?? null}
                  onSettled={refresh}
                />
              ) : (
                <p className="text-sm text-muted">Awaiting review.</p>
              )}
            </Panel>
          </div>
        )}
      </div>
    </div>
  );
}

function VersionCard({
  engagementId,
  version: v,
  selected,
  onSelect,
}: {
  engagementId: string;
  version: ItemVersionOut;
  selected: boolean;
  onSelect: () => void;
}): JSX.Element {
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const save = async (): Promise<void> => {
    setBusy(true);
    setFailure(null);
    try {
      const { data, response } = await content({
        path: { engagement_id: engagementId, version_id: v.id },
        parseAs: "blob",
        throwOnError: true,
      });
      const header = response.headers.get("Content-Disposition") ?? "";
      const name = /filename="([^"]+)"/.exec(header)?.[1] ?? "evidence";
      const url = URL.createObjectURL(data);
      const link = document.createElement("a");
      link.href = url;
      link.download = name;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      const code = errorMessage(error);
      setFailure(code === "integrity_failed" ? "This file couldn't be verified." : code);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div
      className={`flex flex-col gap-1 rounded-[var(--radius-control)] border p-3 text-sm ${
        selected ? "border-accent bg-accent-soft" : "border-line"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button type="button" className="font-semibold hover:underline" onClick={onSelect}>
          Version {v.version_no}
        </button>
        <Button size="sm" variant="outline" disabled={busy} onClick={() => void save()}>
          {busy ? "Downloading…" : "Download"}
        </Button>
      </div>
      <p>
        {v.method === "retrieved"
          ? `Retrieved from ${v.source}${
              v.period_start !== null ? ` · ${v.period_start} to ${v.period_end ?? ""}` : ""
            } · pulled ${when(v.pulled_at)}`
          : `Uploaded by ${v.uploaded_by_name || "the client"}`}
      </p>
      {v.file_name !== null && <p className="break-all">{v.file_name}</p>}
      <p className="text-xs text-muted tabular-nums">
        {when(v.created_at)} · {size(v.size_bytes)} · {v.media_type} ·{" "}
        <span title={v.fingerprint}>{v.fingerprint.slice(0, 12)}</span>
      </p>
      {v.decision !== null && (
        <p className="text-xs">{DECISION_LABEL[v.decision.decision] ?? v.decision.decision}</p>
      )}
      {failure !== null && (
        <p role="alert" className="text-danger">
          {failure}
        </p>
      )}
    </div>
  );
}

function Screening({
  result,
  loading,
}: {
  result: ScreeningResultOut | undefined;
  loading: boolean;
}): JSX.Element {
  return (
    <Panel title="Screening" action={result !== undefined ? <AiTag /> : undefined}>
      {loading ? (
        <Skeleton className="h-16" />
      ) : result === undefined ? (
        <p className="text-sm text-muted">Not screened yet.</p>
      ) : (
        <div className="flex flex-col gap-2 text-sm">
          <p>
            <span className="font-semibold">{ACTION_LABEL[result.action] ?? result.action}</span> ·
            confidence {confidencePercent(result.confidence)}
          </p>
          <AgentText text={result.rationale} />
          {result.citations.length > 0 && (
            <ul aria-label="Citations" className="flex flex-col gap-1">
              {result.citations.map((c, index) => (
                <li
                  key={`${c.cell}-${String(index)}`}
                  className="flex flex-wrap items-center gap-2"
                >
                  <span className="font-mono text-xs">{c.cell}</span>
                  {c.verified ? (
                    <StatusPill tone="success">Verified</StatusPill>
                  ) : (
                    <StatusPill tone="warning">
                      Not verified
                      {c.reason !== null ? `: ${NOT_VERIFIED[c.reason] ?? c.reason}` : ""}
                    </StatusPill>
                  )}
                  {c.quote !== null && <AgentText inline text={c.quote} className="text-muted" />}
                  {c.value !== null && (
                    <AgentText inline text={c.value} className="tabular-nums" />
                  )}
                </li>
              ))}
            </ul>
          )}
          {result.unverified.length > 0 && (
            <div>
              <p className="font-semibold">Claims without a verified source</p>
              <ul className="list-disc pl-5">
                {result.unverified.map((claim, index) => (
                  <li key={`${String(index)}-${claim}`}>
                    <AgentText inline text={claim} />
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}
