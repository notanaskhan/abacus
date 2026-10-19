import type { EngagementOut, RequestItemOut, ScreeningResultOut } from "@abacus/api-client";
import {
  createRequestItemMutation,
  getEngagementOptions,
  meOptions,
  getRetrievalOptions,
  listEvidenceVersionsOptions,
  reviewFlagsOptions,
  listEvidenceVersionsQueryKey,
  listRequestItemsOptions,
  listRequestItemsQueryKey,
  boardSummaryOptions,
  setClientVisibilityMutation,
  setTierMutation,
  listScreeningResultsOptions,
  listScreeningResultsQueryKey,
  startRetrievalMutation,
} from "@abacus/api-client/query";
import {
  AgentText,
  AiTag,
  Alert,
  Badge,
  Button,
  EmptyState,
  Input,
  Label,
  Skeleton,
  Spinner,
  StatusPill,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { type JSX, type ReactNode, type SyntheticEvent, useEffect, useState } from "react";
import { errorMessage } from "../api";
import { DueDatesBar, ItemDue, useDefaultDue } from "./DueDates";
import { GuidanceDrafts } from "./GuidanceDrafts";
import { InboxPanel } from "./InboxPanel";
import { type BoardFilters, TIER_MEANING, applyFilters, readFilters } from "../board/filters";
import {
  type BoardRow,
  awaitingScreening,
  boardRows,
  confidencePercent,
  sourceLabel,
  statusLabel,
} from "../board/join";

const SCREENING_POLL_MS = 3000;
// Stop asking after this long: a run that failed or was skipped never produces a result.
const SCREENING_POLL_LIMIT_MS = 2 * 60_000;
const RETRIEVAL_POLL_MS = 2000;

/** The evidence board for one engagement (SPEC-000 §17, AC-18). */
const MATCH_REQUESTERS = new Set(["engagement_partner", "manager", "senior", "staff"]);
const DRAFTERS = new Set(["engagement_partner", "manager", "senior"]); // SPEC-035

export function Board({
  engagementId,
  actions,
}: {
  engagementId: string;
  /** Page actions for the list's header (the router passes "Import from Excel"). */
  actions?: ReactNode;
}): JSX.Element {
  const path = { path: { engagement_id: engagementId } };
  const engagement = useQuery(getEngagementOptions(path));
  const me = useQuery(meOptions());
  // SPEC-033 (TASK-066): who may ask the matcher ("Suggest with agent").
  const myRole = engagement.data?.team.find((m) => m.user_id === me.data?.user_id)?.role;
  const items = useQuery(listRequestItemsOptions(path));
  const versions = useQuery(listEvidenceVersionsOptions(path));
  const reviewFlags = useQuery({ ...reviewFlagsOptions(path), retry: false });
  const defaultDue = useDefaultDue(engagementId);
  const search = useRouterState({ select: (state) => state.location.search });
  const filters = readFilters(search);
  const navigate = useNavigate();
  const setFilter = (key: keyof BoardFilters, value: string): void => {
    void navigate({
      to: ".",
      search: (previous: Record<string, unknown>) => ({
        ...previous,
        [key]: value === "" ? undefined : value,
      }),
      replace: true,
    });
  };
  const [pollingSince] = useState(() => Date.now());
  // A timer, not a clock read in render: when the cap passes, re-render to offer Check again.
  const [pollingExpired, setPollingExpired] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => {
      setPollingExpired(true);
    }, SCREENING_POLL_LIMIT_MS);
    return () => {
      clearTimeout(timer);
    };
  }, []);
  const results = useQuery({
    ...listScreeningResultsOptions(path),
    // Keep checking while some evidence still waits for the agent's proposal, for a while.
    refetchInterval: (query) =>
      items.data !== undefined &&
      versions.data !== undefined &&
      query.state.data !== undefined &&
      awaitingScreening(boardRows(items.data, versions.data, query.state.data)) &&
      !pollingExpired &&
      Date.now() - pollingSince < SCREENING_POLL_LIMIT_MS
        ? SCREENING_POLL_MS
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
  // SPEC-030 (TASK-059): shown AI flags per version (firm roles only; a refusal shows none).
  const aiFlags = new Map((reviewFlags.data ?? []).map((f) => [f.evidence_version_id, f.flags]));
  const shown = applyFilters(rows, filters, aiFlags);

  return (
    <section aria-labelledby="board-heading" className="flex flex-col gap-3">
      {/* The record header names the engagement (TASK-092); the heading stays for structure. */}
      <h1 id="board-heading" className="sr-only">
        {engagement.data.name}
      </h1>
      <div className="grid grid-cols-1 items-start gap-3 lg:grid-cols-2">
        <InboxPanel
          engagementId={engagementId}
          items={items.data}
          firm={{ canRequestMatch: myRole !== undefined && MATCH_REQUESTERS.has(myRole) }}
        />
        <GuidanceDrafts
          engagementId={engagementId}
          items={items.data}
          canDraft={myRole !== undefined && DRAFTERS.has(myRole)}
        />
      </div>
      {/* One pane for the list (TASK-094): summary and the list's due date, filters, the rows
          in columns, and a row to add a request. */}
      <div className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2">
        <div className="flex min-h-[50px] flex-wrap items-center gap-x-5 gap-y-2 border-b-[0.5px] border-hair px-4 py-2">
          <h2 className="text-[15px] font-medium tracking-[-0.012em]">Requests</h2>
          <SummaryStrip engagementId={engagementId} />
          <span className="flex-1" />
          {rows.length > 0 && (
            <DueDatesBar engagementId={engagementId} items={rows.map((r) => r.item)} />
          )}
          {actions}
        </div>
        {rows.length > 0 && (
          <div className="border-b-[0.5px] border-hair bg-band-hd px-4 py-2">
            <FilterBar
              filters={filters}
              areas={[...new Set(rows.map((r) => r.item.audit_area))].sort()}
              onChange={setFilter}
            />
          </div>
        )}
        {rows.length === 0 ? (
          <EmptyState title="No request items yet">
            Add one to request evidence from the client.
          </EmptyState>
        ) : shown.length === 0 ? (
          <EmptyState title="No items match these filters">
            Clear a filter to see more requests.
          </EmptyState>
        ) : (
          <>
            <div
              aria-hidden="true"
              className={`hidden h-[30px] items-center gap-4 border-b-[0.5px] border-hair px-4 text-[11.5px] text-ink-2 lg:grid ${ROW_GRID}`}
            >
              <span>Request</span>
              <span>Status</span>
              <span>Evidence</span>
              <span>Agent screening</span>
              <span>Due</span>
            </div>
            <ul className="flex flex-col divide-y-[0.5px] divide-hair" aria-label="Request items">
              {shown.map((row) => (
                <li key={row.item.id}>
                  <RequestItemCard
                    row={row}
                    aiFlags={aiFlags.get(row.evidence?.id ?? "") ?? 0}
                    fallbackDue={defaultDue}
                    engagement={engagement.data}
                    pollingExpired={pollingExpired}
                    onRefresh={() => void results.refetch()}
                  />
                </li>
              ))}
            </ul>
          </>
        )}
        <div className="border-t-[0.5px] border-hair bg-band-hd px-4 py-3">
          <AddRequestItem engagementId={engagementId} />
        </div>
      </div>
    </section>
  );
}

const ROW_GRID =
  "lg:grid-cols-[minmax(220px,1.3fr)_120px_minmax(160px,1fr)_minmax(240px,1.6fr)_190px]";

function RequestItemCard({
  row,
  aiFlags,
  fallbackDue,
  engagement,
  pollingExpired,
  onRefresh,
}: {
  row: BoardRow;
  aiFlags: number;
  fallbackDue: string | null | undefined;
  engagement: EngagementOut;
  pollingExpired: boolean;
  onRefresh: () => void;
}): JSX.Element {
  const { item, evidence, screening } = row;
  return (
    <div className="flex flex-col gap-2 px-4 py-3 transition-colors hover:bg-shell/60">
      <div className={`grid grid-cols-1 items-start gap-x-4 gap-y-2 ${ROW_GRID}`}>
        <div className="flex min-w-0 flex-col gap-1">
          <Link
            to="/engagements/$engagementId/items/$itemId"
            params={{ engagementId: item.engagement_id, itemId: item.id }}
            className="text-[13px] font-medium text-ink hover:underline"
          >
            {item.description}
          </Link>
          <p className="flex flex-wrap items-center gap-2 text-[12px] text-ink-3">
            {item.audit_area}
            <TierChip item={item} />
          </p>
        </div>
        <div>
          <StatusPill tone={statusTone(item.status)}>
            <span aria-label={`Status: ${statusLabel(item.status)}`}>
              {statusLabel(item.status)}
            </span>
          </StatusPill>
        </div>
        <div className="flex flex-col items-start gap-1 text-[12.5px]">
          <span className={evidence === null ? "text-ink-3" : ""}>
            {evidence === null
              ? "No evidence yet"
              : `${sourceLabel(evidence)} · version ${String(evidence.version_no)}`}
          </span>
          <span className="flex flex-wrap gap-1">
            {/* SPEC-029 AC-11 (TASK-057): code found something in the latest version. */}
            {evidence !== null && (evidence.problems ?? 0) > 0 && (
              <Badge tone="warning">Problems found</Badge>
            )}
            {evidence !== null && aiFlags > 0 && <Badge tone="warning">AI flags</Badge>}
            {/* SPEC-032 AC-8 (TASK-063): comments on the request and its versions. */}
            {(item.comment_count ?? 0) > 0 && (
              <Badge
                tone={item.unread_comments === true ? "info" : "neutral"}
                aria-label={`${String(item.comment_count)} comments${item.unread_comments === true ? ", unread" : ""}`}
              >
                Comments {item.comment_count}
                {item.unread_comments === true && " •"}
              </Badge>
            )}
          </span>
        </div>
        <div className="min-w-0 text-[12.5px]">
          {screening.kind === "none" ? (
            <span className="text-ink-4">—</span>
          ) : screening.kind === "pending" ? (
            pollingExpired ? (
              <span className="flex items-center gap-2">
                Screening hasn&apos;t finished.
                <Button size="sm" variant="ghost" onClick={onRefresh}>
                  Check again
                </Button>
              </span>
            ) : (
              <Spinner label="Screening…" />
            )
          ) : (
            <ScreeningSummary result={screening.result} />
          )}
        </div>
        <div className="text-[12.5px]">
          <ItemDue item={item} fallback={fallbackDue} />
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-[12px]">
        {(item.status === "open" || item.status === "received") && (
          <Retrieve item={item} engagement={engagement} />
        )}
        <TierOverride item={item} />
        <HiddenFromClient item={item} />
      </div>
    </div>
  );
}

/** SPEC-020 (TASK-035 D3): items are client-visible unless the team hides one. */
function HiddenFromClient({ item }: { item: RequestItemOut }): JSX.Element {
  const queryClient = useQueryClient();
  const change = useMutation({
    ...setClientVisibilityMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: listRequestItemsQueryKey({ path: { engagement_id: item.engagement_id } }),
      });
    },
  });
  const hidden = item.client_visible === false;
  return (
    <label className="ml-auto flex items-center gap-2 text-sm text-muted">
      <input
        type="checkbox"
        checked={hidden}
        disabled={change.isPending}
        onChange={(event) => {
          change.mutate({
            path: { engagement_id: item.engagement_id, item_id: item.id },
            body: { client_visible: !event.target.checked },
          });
        }}
      />
      Hidden from client
      {change.isError && (
        <span role="alert" className="text-danger">
          {errorMessage(change.error)}
        </span>
      )}
    </label>
  );
}

/** The agent's proposal: labelled as one, model text shown only through AgentText (ADR-065). */
function ScreeningSummary({ result }: { result: ScreeningResultOut }): JSX.Element {
  return (
    <div className="flex flex-col gap-1.5" aria-label="Screening result">
      <p className="flex flex-wrap items-center gap-1.5">
        <AiTag />
        <span className="text-ink-3">Agent proposes:</span>
        <Badge tone={result.action === "ready_for_review" ? "success" : "warning"}>
          {result.action === "ready_for_review" ? "Ready for review" : "Needs revision"}
        </Badge>
        <span className="text-[11.5px] text-ink-3">
          confidence {confidencePercent(result.confidence)}
        </span>
      </p>
      <AgentText text={result.rationale} className="text-[12.5px] leading-[1.45] text-ink-2" />
      {result.citations.length > 0 && (
        <ul className="flex flex-wrap gap-x-3 gap-y-1" aria-label="Citations">
          {result.citations.map((c) => (
            <li key={c.cell} className="flex items-center gap-1.5 text-[12px]">
              <Badge tone={c.verified ? "success" : "danger"}>
                {c.verified ? "Verified" : "Unverified"}
              </Badge>
              <span className="font-mono text-[11.5px] text-ink-2">
                <span className="sr-only">Cell </span>
                <AgentText inline text={c.cell} />
              </span>
              {c.quote !== null && <AgentText inline text={`“${c.quote}”`} />}
              {c.value !== null && <AgentText inline text={c.value} />}
            </li>
          ))}
        </ul>
      )}
      {result.unverified.length > 0 && (
        <div>
          <p className="text-muted">Couldn't be verified:</p>
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
  const engagementId = engagement.id;
  const path = { engagement_id: engagementId };
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
    refetchInterval: (query) => (isActive(query.state.data?.status) ? RETRIEVAL_POLL_MS : false),
  });
  const status = run.data?.status ?? null;
  // Busy from the click until the run ends (no gap between the start and its first poll). A run
  // waiting for capacity (`queued`, SPEC-003) hasn't ended either.
  const running = start.isPending || (runId !== null && (status === null || isActive(status)));
  const finished = status !== null && !isActive(status);
  // Refresh the board once when the retrieval ends: an effect, never a side effect in render.
  useEffect(() => {
    if (!finished) return;
    const board = { path: { engagement_id: engagementId } };
    void queryClient.invalidateQueries({ queryKey: listRequestItemsQueryKey(board) });
    void queryClient.invalidateQueries({ queryKey: listEvidenceVersionsQueryKey(board) });
    void queryClient.invalidateQueries({ queryKey: listScreeningResultsQueryKey(board) });
  }, [finished, runId, engagementId, queryClient]);

  return (
    <div className="flex items-center gap-3">
      <Button
        variant="outline"
        size="sm"
        disabled={running}
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
      {running && status !== "queued" && <Spinner label="Retrieving…" />}
      {status === "queued" && (
        <Spinner label={queuedLabel(run.data?.estimated_start_at ?? null)} />
      )}
      {status === "failed_validation" && (
        <span className="text-sm text-danger">The trial balance didn't pass validation.</span>
      )}
      {status === "failed" && (
        <span className="text-sm text-danger">Retrieval failed. Try again.</span>
      )}
      {start.isError && <span className="text-sm text-danger">{errorMessage(start.error)}</span>}
    </div>
  );
}

function isActive(status: string | undefined | null): boolean {
  return status === "running" || status === "queued";
}

// Waiting for capacity, in plain words: never names another firm (SPEC-003 §17).
function queuedLabel(estimatedStartAt: string | null): string {
  if (estimatedStartAt === null) return "Queued: waiting for capacity";
  const time = new Date(estimatedStartAt).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
  return `Queued: expected to start by ${time}`;
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
    <div>
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
        <Button type="submit" variant="outline" disabled={mutation.isPending}>
          Add request item
        </Button>
      </form>
      {mutation.isError && (
        <div className="mt-3">
          <Alert title="Couldn't add the request item">{errorMessage(mutation.error)}</Alert>
        </div>
      )}
    </div>
  );
}

function statusTone(status: RequestItemOut["status"]): "neutral" | "success" | "warning" {
  return status === "ready_for_review"
    ? "success"
    : status === "needs_revision"
      ? "warning"
      : "neutral";
}

const STATUS_FILTERS: [string, string][] = [
  ["open", "Open"],
  ["received", "Received"],
  ["ready_for_review", "Ready for review"],
  ["needs_revision", "Needs revision"],
  ["accepted", "Accepted"],
];
const SELECT_CLASS =
  "h-[26px] rounded-[6px] border-0 bg-card px-2 text-[12.5px] text-ink shadow-e1 hover:bg-nav-fill";

/** SPEC-022 AC-5: narrow the list; every choice lives in the URL. */
function FilterBar({
  filters,
  areas,
  onChange,
}: {
  filters: BoardFilters;
  areas: string[];
  onChange: (key: keyof BoardFilters, value: string) => void;
}): JSX.Element {
  const select = (
    key: keyof BoardFilters,
    label: string,
    options: [string, string][],
  ): JSX.Element => (
    <label className="flex items-center gap-1.5 text-[12px] text-ink-3">
      {label}
      <select
        className={SELECT_CLASS}
        value={filters[key] ?? ""}
        onChange={(event) => {
          onChange(key, event.target.value);
        }}
      >
        <option value="">All</option>
        {options.map(([value, text]) => (
          <option key={value} value={value}>
            {text}
          </option>
        ))}
      </select>
    </label>
  );
  return (
    <div
      role="search"
      aria-label="Filter requests"
      className="flex flex-wrap items-center gap-x-4 gap-y-2"
    >
      {select("status", "Status", STATUS_FILTERS)}
      {select(
        "area",
        "Audit area",
        areas.map((a) => [a, a]),
      )}
      {select("tier", "Tier", [
        ...Object.keys(TIER_MEANING).map((t): [string, string] => [t, `Tier ${t}`]),
        ["none", "Unclassified"],
      ])}
      {select("source", "Evidence", [
        ["retrieved", "Retrieved"],
        ["imported", "Imported"],
        ["uploaded", "Uploaded"],
        ["none", "None yet"],
        ["problems", "Problems found"],
        ["ai_flags", "AI flags"],
        ["unread_comments", "Unread comments"],
      ])}
      {select("assignee", "Client assignee", [
        ["assigned", "Assigned"],
        ["unassigned", "Unassigned"],
      ])}
      <label className="ml-auto flex items-center gap-1.5 text-[12px] text-ink-3">
        Search
        <input
          type="search"
          className={SELECT_CLASS}
          value={filters.q ?? ""}
          onChange={(event) => {
            onChange("q", event.target.value);
          }}
        />
      </label>
    </div>
  );
}

/** SPEC-022 AC-5: counts, "retrieved, never asked" and the retrievable share. */
function SummaryStrip({ engagementId }: { engagementId: string }): JSX.Element | null {
  const summary = useQuery({
    ...boardSummaryOptions({ path: { engagement_id: engagementId } }),
    retry: false,
  });
  if (summary.data === undefined) return null;
  const s = summary.data;
  const share = s.retrievable_share;
  return (
    <dl aria-label="Board summary" className="flex flex-wrap items-baseline gap-x-5 gap-y-1">
      {(
        [
          ["Requests", String(s.total)],
          ["Retrieved, never asked", String(s.retrieved_never_asked)],
          ["Retrievable share", share === null ? "—" : `${String(Math.round(share * 100))}%`],
          ["Unclassified", String(s.unclassified)],
        ] as const
      ).map(([label, value]) => (
        <div key={label} className="flex items-baseline gap-1.5">
          <dt className="text-[12px] text-ink-3">{label}</dt>
          <dd className="text-[13px] font-medium tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function TierChip({ item }: { item: RequestItemOut }): JSX.Element {
  const tier = item.retrievability_tier;
  if (tier == null) return <span className="text-xs">Unclassified</span>;
  const unavailable = tier === "A" && item.dataset != null && item.available !== true;
  return (
    <span className="inline-flex items-center gap-1 text-xs">
      <span
        title={TIER_MEANING[tier]}
        className="rounded-[4px] bg-nested px-1.5 py-px font-medium text-ink-2"
      >
        Tier {tier}
      </span>
      {item.tier_source === "override" && <span>(set by the team)</span>}
      {unavailable && <span>· not available from the connected system</span>}
    </span>
  );
}

/** SPEC-022 AC-2: the team can set a tier, or let the rules decide again. */
function TierOverride({ item }: { item: RequestItemOut }): JSX.Element {
  const queryClient = useQueryClient();
  const change = useMutation({
    ...setTierMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: listRequestItemsQueryKey({ path: { engagement_id: item.engagement_id } }),
      });
    },
  });
  const value = item.tier_source === "override" ? (item.retrievability_tier ?? "") : "";
  return (
    <label className="flex items-center gap-2 text-sm text-muted">
      Tier
      <select
        aria-label={`Tier for ${item.description}`}
        className={SELECT_CLASS}
        value={value}
        disabled={change.isPending}
        onChange={(event) => {
          const next = event.target.value;
          change.mutate({
            path: { engagement_id: item.engagement_id, item_id: item.id },
            body: { tier: next === "" ? null : (next as "A" | "B" | "C" | "D" | "E") },
          });
        }}
      >
        <option value="">Automatic</option>
        {Object.keys(TIER_MEANING).map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>
      {change.isError && (
        <span role="alert" className="text-danger">
          {errorMessage(change.error)}
        </span>
      )}
    </label>
  );
}
