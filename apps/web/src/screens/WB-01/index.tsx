// WB-01 Workbench › Sessions (W-02-T08 skeleton, W-02-T14 list pane and header; docs/screens/
// WB-01.md; SPEC-653). The T4 frame with the session list from the server (DEC-87 membership, walls
// applied before it answers) and the selected session's header. W-02-T14: the list is bound to its
// query and the realtime invalidations (`user:<me>`, `session:<id>`), the FilterButton menu reads
// C2's words with the server's counts ("Running 3"; 9:25 reads "Running 4" when #4127 starts), title
// search with the f empty state ("No sessions match 'K-3'."), row markers (amber dot, spinner, Ready
// for review), "· via Agent" through `formatActor` (INV-5), inline rename and the delete dialog on
// rows the server lets the viewer manage (AC-L4, AC-L5), and the header: Bug opens the run trace
// (WB-09), the Paperclip chip names the context count, Create Agent… is a planned link (W-03). W-02-T17:
// the thread states (Thread.tsx); a locked row never draws the session's content (INV-3).
import type { SessionSnapshotOut, SessionSummaryOut } from "@abacus/api-client";
import {
  ChatHeader,
  ConfirmDialog,
  ErrorState,
  type MenuItem,
  RestrictedState,
  type SessionRow,
  SessionList,
  WorkbenchLayout,
  registryWord,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { useOpenOverlay } from "../../app-core/open";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useRealtimeStream } from "../../app-core/realtime-hooks";
import { useSession } from "../../app-core/session";
import {
  SESSION_FILTERS,
  type SessionFilter,
  useDeleteSession,
  useRenameSession,
  useWorkbenchSession,
  useWorkbenchSessions,
  workbenchTopics,
} from "../../domain/workbench";
import { hrefOf, to } from "../../routes/to";
import { COPY } from "./copy";
import { Thread } from "./Thread";

export interface WB01Props {
  filter: SessionFilter;
  q: string;
  sessionId: string | null;
  onQuery: (q: string) => void;
  onSelect: (sessionId: string) => void;
  /** The list's "+": opens WB-02 at the href it is given. */
  onNew: (href: string) => void;
  /** W-02-T14: the FilterButton menu's choice (the route writes `?filter=`). */
  onFilter?: (filter: SessionFilter) => void;
  /** W-02-T14: Create Agent… (WB-07, W-03): a planned link, hidden in production. */
  onCreateAgent?: () => void;
}

/** A server row as the kit's row: the attribution is `formatActor`'s (INV-5). */
export function rowOf(r: SessionSummaryOut, viewerId?: string | null): SessionRow {
  const name = r.owner?.name ?? "";
  return {
    id: r.id,
    title: r.title,
    owner:
      r.owner?.via_agent === true
        ? { kind: "agent_assisted", person: name }
        : { kind: "human", name },
    last_at: r.last_item_at ?? "",
    state: r.state,
    needs_answer: r.needs_answer === true,
    running: r.running === true,
    locked: r.locked === true,
    ready_for_review: r.ready_for_review === true,
    // Rename and delete are the owner's (AC-L5); the server refuses anyone else with 403.
    manageable:
      r.locked !== true &&
      viewerId !== undefined &&
      viewerId !== null &&
      r.owner?.user_id === viewerId &&
      r.owner.via_agent !== true,
  };
}

/** The FilterButton menu: C2's words, `{n}` filled from the server's counts (never counted here,
 * so a walled session adds nothing: INV-3, DEC-43). */
export function filterLabel(
  filter: SessionFilter,
  counts: { running?: number; needs_answer?: number } | null | undefined,
): string {
  const n =
    filter === "running"
      ? counts?.running
      : filter === "needs_answer"
        ? counts?.needs_answer
        : undefined;
  return registryWord("workbench_session_filter", filter, { fill: { n: String(n ?? 0) } }).label;
}

export function filterMenu(
  active: SessionFilter,
  counts: { running?: number; needs_answer?: number } | null | undefined,
  onFilter: ((f: SessionFilter) => void) | undefined,
): MenuItem[][] {
  return [
    SESSION_FILTERS.map((f) => ({
      label: filterLabel(f, counts),
      checked: f === active,
      onSelect: () => onFilter?.(f),
    })),
  ];
}

function lastRunId(snapshot: SessionSnapshotOut | undefined): string | null {
  const items = snapshot?.items ?? [];
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const run = items[i]?.run_id;
    if (run !== null && run !== undefined) return run;
  }
  return null;
}

export function WB01({
  filter,
  q,
  sessionId,
  onQuery,
  onSelect,
  onNew,
  onFilter,
  onCreateAgent,
}: WB01Props): JSX.Element {
  const me = useSession().user?.id ?? null;
  useRealtimeStream(workbenchTopics(me, sessionId));
  const list = useWorkbenchSessions({ filter, q });
  const rows = list.data?.items ?? [];
  const selected = rows.find((r) => r.id === sessionId) ?? null;
  const snapshot = useWorkbenchSession(selected !== null && !selected.locked ? sessionId : null);
  const rename = useRenameSession();
  const remove = useDeleteSession();
  const openOverlay = useOpenOverlay();
  const [deleting, setDeleting] = useState<string | null>(null);
  const runId = lastRunId(snapshot.data);
  const manage = snapshot.data?.allowed_actions.includes("manage") === true;
  return (
    <>
      <WorkbenchLayout
        tab="sessions"
        list={
          list.isError ? (
            <ErrorState noun="sessions" onRetry={() => void list.refetch()} />
          ) : (
            <SessionList
              rows={rows.map((r) => rowOf(r, me))}
              {...(sessionId === null ? {} : { selectedId: sessionId })}
              query={q}
              {...(q.trim() === "" ? {} : { emptyTitle: COPY.noMatch(q.trim()) })}
              filterMenu={filterMenu(filter, list.data?.counts, onFilter)}
              onQuery={onQuery}
              onSelect={onSelect}
              onNew={() => {
                onNew(hrefOf(to.WB02()));
              }}
              onRename={(id, title) => {
                const r = rows.find((x) => x.id === id);
                if (r !== undefined) void rename.rename(id, title, r.version ?? "1");
              }}
              onDelete={setDeleting}
            />
          )
        }
        chat={
          selected?.locked === true ? (
            <RestrictedState reason="walled" title={COPY.lockedTitle} />
          ) : (
            <div data-wb01="thread" className="flex min-h-0 flex-1 flex-col">
              {selected !== null ? (
                <ChatHeader
                  title={selected.title}
                  owner={rowOf(selected).owner}
                  live={selected.running === true}
                  contextCount={selected.context_count ?? 0}
                  {...(runId === null
                    ? {}
                    : {
                        onOpenTrace: () => {
                          openOverlay({ key: "run-trace", args: [runId] });
                        },
                      })}
                  {...(manage
                    ? {
                        onDelete: () => {
                          setDeleting(selected.id);
                        },
                      }
                    : {})}
                  {...(PLANNED_VISIBLE && onCreateAgent !== undefined ? { onCreateAgent } : {})}
                />
              ) : null}
              {selected !== null && sessionId !== null ? (
                <Thread
                  snapshot={snapshot.data}
                  sessionId={sessionId}
                  onOpenRun={(run) => {
                    openOverlay({ key: "run-trace", args: [run] });
                  }}
                />
              ) : null}
            </div>
          )
        }
      />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => {
          if (!open) setDeleting(null);
        }}
        title={COPY.deleteConfirm}
        confirmLabel={COPY.delete}
        onConfirm={() => {
          if (deleting !== null) void remove.remove(deleting);
        }}
      />
    </>
  );
}
