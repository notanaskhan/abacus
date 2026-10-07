import type { EngagementOut, RequestItemOut, ScreeningResultOut } from "@abacus/api-client";
import {
  createRequestItemMutation,
  getEngagementOptions,
  getRetrievalOptions,
  listEvidenceVersionsOptions,
  listEvidenceVersionsQueryKey,
  listRequestItemsOptions,
  listRequestItemsQueryKey,
  listScreeningResultsOptions,
  listScreeningResultsQueryKey,
  startRetrievalMutation,
} from "@abacus/api-client/query";
import {
  AgentText,
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  Label,
  Skeleton,
  Spinner,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type SyntheticEvent, type JSX, useState } from "react";
import { errorMessage } from "../api";
import {
  type BoardRow,
  awaitingScreening,
  boardRows,
  confidencePercent,
  sourceLabel,
  statusLabel,
} from "../board/join";

const SCREENING_POLL_MS = 3000;
const RETRIEVAL_POLL_MS = 2000;

/** The evidence board for one engagement (SPEC-000 §17, AC-18). */
export function Board({ engagementId }: { engagementId: string }): JSX.Element {
  const path = { path: { engagement_id: engagementId } };
  const engagement = useQuery(getEngagementOptions(path));
  const items = useQuery(listRequestItemsOptions(path));
  const versions = useQuery(listEvidenceVersionsOptions(path));
  const results = useQuery({
    ...listScreeningResultsOptions(path),
    // Keep checking while some evidence still waits for the agent's proposal.
    refetchInterval: (query) =>
      items.data !== undefined && versions.data !== undefined && query.state.data !== undefined
        ? awaitingScreening(boardRows(items.data, versions.data, query.state.data))
          ? SCREENING_POLL_MS
          : false
        : false,
  });

  if (engagement.isPending || items.isPending || versions.isPending || results.isPending) {
    return (
      <div className="flex flex-col gap-3" aria-busy="true">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </div>
    );
  }
  const failed = [engagement, items, versions, results].find((q) => q.isError);
  if (failed !== undefined) {
    return (
      <Alert
        title="Couldn't load the evidence board"
        action={
          <Button size="sm" variant="outline" onClick={() => void failed.refetch()}>
            Retry
          </Button>
        }
      >
        {errorMessage(failed.error)}
      </Alert>
    );
  }
  if (
    engagement.data === undefined ||
    items.data === undefined ||
    versions.data === undefined ||
    results.data === undefined
  ) {
    return <Spinner label="Loading…" />;
  }
  const rows = boardRows(items.data, versions.data, results.data);

  return (
    <section aria-labelledby="board-heading" className="flex flex-col gap-4">
      <div>
        <h1 id="board-heading" className="text-xl font-semibold">
          {engagement.data.name}
        </h1>
        <p className="text-sm text-neutral-600">
          {engagement.data.client_name} — {engagement.data.client_entity_name} ·{" "}
          {engagement.data.fiscal_period_start} to {engagement.data.fiscal_period_end}
        </p>
      </div>
      <AddRequestItem engagementId={engagementId} />
      {rows.length === 0 ? (
        <EmptyState title="No request items yet">
          Add one to request evidence from the client.
        </EmptyState>
      ) : (
        <ul className="flex flex-col gap-3" aria-label="Request items">
          {rows.map((row) => (
            <li key={row.item.id}>
              <RequestItemCard row={row} engagement={engagement.data} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function RequestItemCard({
  row,
  engagement,
}: {
  row: BoardRow;
  engagement: EngagementOut;
}): JSX.Element {
  const { item, evidence, screening } = row;
  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-medium">{item.description}</p>
          <p className="text-sm text-neutral-600">{item.audit_area}</p>
        </div>
        <Badge tone={statusTone(item.status)} aria-label={`Status: ${statusLabel(item.status)}`}>
          {statusLabel(item.status)}
        </Badge>
      </div>
      <dl className="grid grid-cols-[8rem_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-neutral-600">Source</dt>
        <dd>
          {evidence === null
            ? "No evidence yet"
            : `${sourceLabel(evidence)} · version ${String(evidence.version_no)}`}
        </dd>
        <dt className="text-neutral-600">Screening</dt>
        <dd>
          {screening.kind === "none" ? (
            "—"
          ) : screening.kind === "pending" ? (
            <Spinner label="Screening…" />
          ) : (
            <ScreeningSummary result={screening.result} />
          )}
        </dd>
      </dl>
      {(item.status === "open" || item.status === "received") && (
        <Retrieve item={item} engagement={engagement} />
      )}
    </Card>
  );
}

/** The agent's proposal: labelled as one, model text shown only through AgentText (ADR-065). */
function ScreeningSummary({ result }: { result: ScreeningResultOut }): JSX.Element {
  return (
    <div className="flex flex-col gap-2" aria-label="Screening result">
      <p>
        <span className="text-neutral-600">Agent proposes: </span>
        <Badge tone={result.action === "ready_for_review" ? "success" : "warning"}>
          {result.action === "ready_for_review" ? "Ready for review" : "Needs revision"}
        </Badge>{" "}
        <span className="text-neutral-600">confidence {confidencePercent(result.confidence)}</span>
      </p>
      <AgentText text={result.rationale} className="text-neutral-800" />
      {result.citations.length > 0 && (
        <ul className="flex flex-col gap-1" aria-label="Citations">
          {result.citations.map((c) => (
            <li key={c.cell} className="flex items-center gap-2">
              <Badge tone={c.verified ? "success" : "danger"}>
                {c.verified ? "Verified" : "Unverified"}
              </Badge>
              <span>Cell {c.cell}</span>
              {c.quote !== null && <AgentText inline text={`“${c.quote}”`} />}
              {c.value !== null && <span>{c.value}</span>}
            </li>
          ))}
        </ul>
      )}
      {result.unverified.length > 0 && (
        <div>
          <p className="text-neutral-600">Couldn't be verified:</p>
          <ul className="list-disc pl-5">
            {result.unverified.map((note, i) => (
              <li key={`${String(i)}-${note}`}>
                <AgentText inline text={note} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Retrieve({
  item,
  engagement,
}: {
  item: RequestItemOut;
  engagement: EngagementOut;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { engagement_id: engagement.id };
  const [runId, setRunId] = useState<string | null>(null);
  const start = useMutation({
    ...startRetrievalMutation(),
    onSuccess: (run) => {
      setRunId(run.sync_run_id);
    },
  });
  const run = useQuery({
    ...getRetrievalOptions({ path: { ...path, sync_run_id: runId ?? "" } }),
    enabled: runId !== null,
    refetchInterval: (query) =>
      query.state.data?.status === "running" ? RETRIEVAL_POLL_MS : false,
  });
  const status = run.data?.status ?? (start.isPending ? "running" : null);
  const finished = status !== null && status !== "running";
  if (finished && run.isFetchedAfterMount) {
    void queryClient.invalidateQueries({ queryKey: listRequestItemsQueryKey({ path }) });
    void queryClient.invalidateQueries({ queryKey: listEvidenceVersionsQueryKey({ path }) });
    void queryClient.invalidateQueries({ queryKey: listScreeningResultsQueryKey({ path }) });
  }

  return (
    <div className="flex items-center gap-3">
      <Button
        variant="outline"
        size="sm"
        disabled={status === "running"}
        onClick={() => {
          start.mutate({
            path,
            body: {
              request_item_id: item.id,
              period_start: engagement.fiscal_period_start,
              period_end: engagement.fiscal_period_end,
            },
          });
        }}
      >
        Retrieve trial balance
      </Button>
      {status === "running" && <Spinner label="Retrieving…" />}
      {status === "failed_validation" && (
        <span className="text-sm text-red-800">The trial balance didn't pass validation.</span>
      )}
      {status === "failed" && (
        <span className="text-sm text-red-800">Retrieval failed. Try again.</span>
      )}
      {start.isError && <span className="text-sm text-red-800">{errorMessage(start.error)}</span>}
    </div>
  );
}

function AddRequestItem({ engagementId }: { engagementId: string }): JSX.Element {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    ...createRequestItemMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: listRequestItemsQueryKey({ path: { engagement_id: engagementId } }),
      });
    },
  });

  function submit(event: SyntheticEvent<HTMLFormElement>): void {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const text = (name: string): string => {
      const value = form.get(name);
      return typeof value === "string" ? value : "";
    };
    mutation.mutate(
      {
        path: { engagement_id: engagementId },
        body: { description: text("description"), audit_area: text("audit_area") },
      },
      {
        onSuccess: () => {
          formElement.reset();
        },
      },
    );
  }

  return (
    <Card>
      <form
        onSubmit={submit}
        className="flex flex-wrap items-end gap-3"
        aria-label="Add request item"
      >
        <div className="flex min-w-64 flex-1 flex-col gap-1">
          <Label htmlFor="description">Request</Label>
          <Input
            id="description"
            name="description"
            required
            placeholder="Trial balance for the fiscal year"
          />
        </div>
        <div className="flex w-48 flex-col gap-1">
          <Label htmlFor="audit_area">Audit area</Label>
          <Input id="audit_area" name="audit_area" required placeholder="General" />
        </div>
        <Button type="submit" disabled={mutation.isPending}>
          Add request item
        </Button>
      </form>
      {mutation.isError && (
        <div className="mt-3">
          <Alert title="Couldn't add the request item">{errorMessage(mutation.error)}</Alert>
        </div>
      )}
    </Card>
  );
}

function statusTone(status: RequestItemOut["status"]): "neutral" | "success" | "warning" {
  return status === "ready_for_review"
    ? "success"
    : status === "needs_revision"
      ? "warning"
      : "neutral";
}
