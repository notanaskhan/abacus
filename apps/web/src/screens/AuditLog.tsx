import type { AuditEventsData, EventOut } from "@abacus/api-client";
import { auditEvents } from "@abacus/api-client";
import { auditFacetsOptions } from "@abacus/api-client/query";
import { Alert, Badge, Button, EmptyState, Skeleton } from "@abacus/ui";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";

// SPEC-304 (TASK-305): the firm's audit trail, newest first, filtered and paged. Events carry
// identifiers only (ADR-007), so a row shows who, what, on what, and the references; nothing else.

type Query = NonNullable<AuditEventsData["query"]>;

const KIND: Record<string, string> = {
  human: "Person",
  agent: "Agent",
  system: "System",
  support: "Support",
};

/** "finding.severity_concluded" → "Finding · severity concluded". */
export function actionLabel(action: string): string {
  const [noun = "", verb = ""] = action.split(".");
  const words = (s: string): string => s.replaceAll("_", " ");
  const head = words(noun);
  return `${head.charAt(0).toUpperCase()}${head.slice(1)} · ${words(verb)}`;
}

/** The query sent for a set of filters: empty fields left out; dates as whole days (UTC). */
export function toQuery(f: Filters): Query {
  const q: Query = {};
  if (f.action !== "") q.action = f.action;
  if (f.actorKind !== "") q.actor_kind = f.actorKind as NonNullable<Query["actor_kind"]>;
  if (f.targetType !== "") q.target_type = f.targetType;
  if (f.targetId.trim() !== "") q.target_id = f.targetId.trim();
  if (f.from !== "") q.since = `${f.from}T00:00:00Z`;
  if (f.to !== "") {
    const next = new Date(`${f.to}T00:00:00Z`);
    next.setUTCDate(next.getUTCDate() + 1);
    q.until = next.toISOString();
  }
  return q;
}

type Filters = {
  action: string;
  actorKind: string;
  targetType: string;
  targetId: string;
  from: string;
  to: string;
};

const EMPTY: Filters = {
  action: "",
  actorKind: "",
  targetType: "",
  targetId: "",
  from: "",
  to: "",
};

function refs(r: Record<string, string | number> | null | undefined): string {
  if (r == null) return "";
  return Object.entries(r)
    .map(
      ([k, v]) =>
        `${k}=${typeof v === "string" && v.length > 12 ? `${v.slice(0, 8)}…` : String(v)}`,
    )
    .join(" ");
}

function csv(rows: EventOut[]): string {
  const cell = (v: string | number): string => `"${String(v).replaceAll('"', '""')}"`;
  const head = [
    "seq",
    "occurred_at",
    "actor_kind",
    "actor",
    "action",
    "target_type",
    "target_id",
    "before",
    "after",
    "trace_id",
  ];
  return [
    head.join(","),
    ...rows.map((e) =>
      [
        e.seq,
        e.occurred_at,
        e.actor_kind,
        e.actor_name ?? e.actor_id,
        e.action,
        e.target_type,
        e.target_id,
        JSON.stringify(e.before_ref ?? null),
        JSON.stringify(e.after_ref ?? null),
        e.trace_id ?? "",
      ]
        .map(cell)
        .join(","),
    ),
  ].join("\n");
}

export function AuditLog(): JSX.Element {
  const [draft, setDraft] = useState<Filters>(EMPTY);
  const [applied, setApplied] = useState<Filters>(EMPTY);
  const facets = useQuery({ ...auditFacetsOptions(), retry: false });
  const query = toQuery(applied);
  const pages = useInfiniteQuery({
    queryKey: ["auditEvents", query],
    initialPageParam: undefined as number | undefined,
    queryFn: async ({ pageParam }) => {
      const { data } = await auditEvents({
        query: { ...query, ...(pageParam === undefined ? {} : { before: pageParam }) },
        throwOnError: true,
      });
      return data;
    },
    getNextPageParam: (last) => last.next_before ?? undefined,
    retry: false,
  });
  const rows = pages.data?.pages.flatMap((p) => p.events) ?? [];
  const select =
    "h-[30px] rounded-tile border-0 bg-nested px-2 text-[13px] inset-shadow-hair focus:bg-card";
  const set = (patch: Partial<Filters>): void => {
    setDraft({ ...draft, ...patch });
  };
  const download = (): void => {
    const url = URL.createObjectURL(new Blob([csv(rows)], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "audit-log.csv";
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <section
      aria-labelledby="audit-heading"
      className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2"
    >
      <div className="flex min-h-[50px] items-center gap-2 border-b-[0.5px] border-hair px-4">
        <h2 id="audit-heading" className="text-[15px] font-medium tracking-[-0.012em]">
          Audit log
        </h2>
        <span className="text-[12.5px] text-ink-3">
          Every change, as recorded. Identifiers only; nothing here can be edited.
        </span>
        <span className="flex-1" />
        <Button size="sm" variant="outline" disabled={rows.length === 0} onClick={download}>
          Download CSV
        </Button>
      </div>
      <form
        aria-label="Filters"
        className="flex flex-wrap items-end gap-2 border-b-[0.5px] border-hair px-4 py-3 text-[12px] text-ink-3"
        onSubmit={(e) => {
          e.preventDefault();
          setApplied(draft);
        }}
      >
        <label className="flex flex-col gap-1">
          Action
          <select
            aria-label="Action"
            value={draft.action}
            onChange={(e) => {
              set({ action: e.target.value });
            }}
            className={`${select} max-w-[240px]`}
          >
            <option value="">Any</option>
            {(facets.data?.actions ?? []).map((a) => (
              <option key={a} value={a}>
                {actionLabel(a)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          Actor
          <select
            aria-label="Actor"
            value={draft.actorKind}
            onChange={(e) => {
              set({ actorKind: e.target.value });
            }}
            className={select}
          >
            <option value="">Anyone</option>
            {Object.entries(KIND).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          Target
          <select
            aria-label="Target type"
            value={draft.targetType}
            onChange={(e) => {
              set({ targetType: e.target.value });
            }}
            className={select}
          >
            <option value="">Any</option>
            {(facets.data?.target_types ?? []).map((t) => (
              <option key={t} value={t}>
                {t.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          Target ID
          <input
            aria-label="Target ID"
            value={draft.targetId}
            maxLength={200}
            onChange={(e) => {
              set({ targetId: e.target.value });
            }}
            className={`${select} w-[220px] font-mono`}
          />
        </label>
        <label className="flex flex-col gap-1">
          From
          <input
            type="date"
            aria-label="From"
            value={draft.from}
            onChange={(e) => {
              set({ from: e.target.value });
            }}
            className={select}
          />
        </label>
        <label className="flex flex-col gap-1">
          To
          <input
            type="date"
            aria-label="To"
            value={draft.to}
            onChange={(e) => {
              set({ to: e.target.value });
            }}
            className={select}
          />
        </label>
        <Button size="sm" type="submit">
          Apply
        </Button>
        <Button
          size="sm"
          variant="ghost"
          type="button"
          onClick={() => {
            setDraft(EMPTY);
            setApplied(EMPTY);
          }}
        >
          Clear
        </Button>
      </form>
      {pages.isPending ? (
        <Skeleton className="m-4 h-40" />
      ) : pages.isError ? (
        <div className="p-4">
          <Alert title="The audit log isn't available">
            {errorMessage(pages.error) === "forbidden"
              ? "The audit log is for firm admins, the practice leader and the quality partner."
              : errorMessage(pages.error)}
          </Alert>
        </div>
      ) : rows.length === 0 ? (
        <EmptyState title="No events match">Try wider filters.</EmptyState>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[12.5px]">
            <caption className="sr-only">Audit events</caption>
            <thead className="text-left text-[11.5px] text-ink-3">
              <tr className="border-b-[0.5px] border-hair">
                <th className="px-4 py-2 font-normal">When</th>
                <th className="px-2 py-2 font-normal">Who</th>
                <th className="px-2 py-2 font-normal">Action</th>
                <th className="px-2 py-2 font-normal">Target</th>
                <th className="px-4 py-2 font-normal">References</th>
              </tr>
            </thead>
            <tbody className="divide-y-[0.5px] divide-hair">
              {rows.map((e) => (
                <tr key={e.seq} className="align-top">
                  <td className="px-4 py-2 whitespace-nowrap text-ink-2 tabular-nums">
                    {new Date(e.occurred_at).toLocaleString()}
                  </td>
                  <td className="px-2 py-2">
                    <span className="flex items-center gap-1.5">
                      {e.actor_kind !== "human" && (
                        <Badge tone="neutral">{KIND[e.actor_kind] ?? e.actor_kind}</Badge>
                      )}
                      <span className="truncate">{e.actor_name ?? e.actor_id}</span>
                    </span>
                  </td>
                  <td className="px-2 py-2">{actionLabel(e.action)}</td>
                  <td className="px-2 py-2">
                    <button
                      type="button"
                      title="Show this target's history"
                      onClick={() => {
                        const next = {
                          ...EMPTY,
                          targetType: e.target_type,
                          targetId: e.target_id,
                        };
                        setDraft(next);
                        setApplied(next);
                      }}
                      className="text-left hover:underline"
                    >
                      <span className="text-ink-2">{e.target_type.replaceAll("_", " ")}</span>{" "}
                      <span className="font-mono text-[11.5px] text-ink-3">
                        {e.target_id.slice(0, 8)}
                      </span>
                    </button>
                  </td>
                  <td className="px-4 py-2 font-mono text-[11px] text-ink-3">
                    {e.before_ref != null && (
                      <span className="block">{`before ${refs(e.before_ref)}`}</span>
                    )}
                    {e.after_ref != null && (
                      <span className="block">{`after ${refs(e.after_ref)}`}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-center gap-2 px-4 py-3 text-[12px] text-ink-3">
            <span className="tabular-nums">{`${String(rows.length)} shown`}</span>
            {pages.hasNextPage && (
              <Button
                size="sm"
                variant="outline"
                disabled={pages.isFetchingNextPage}
                onClick={() => void pages.fetchNextPage()}
              >
                Load older
              </Button>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
