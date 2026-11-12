// WB-01 Workbench › Sessions (W-02-T08 skeleton; docs/screens/WB-01.md; SPEC-653). The T4 frame
// with the session list from the server (DEC-87 membership, walls applied before it answers) and
// the selected session's thread. The thread states a–g are W-02-T14 and T17's; this skeleton
// routes the list, the filter and title search params, the "+" link to WB-02 and the locked row,
// which never draws the session's content (INV-3).
import type { SessionSummaryOut } from "@abacus/api-client";
import {
  ErrorState,
  RestrictedState,
  type SessionRow,
  SessionList,
  WorkbenchLayout,
} from "@abacus/ui";
import type { JSX } from "react";
import { type SessionFilter, useWorkbenchSessions } from "../../domain/workbench";
import { hrefOf, to } from "../../routes/to";
import { COPY } from "./copy";

export interface WB01Props {
  filter: SessionFilter;
  q: string;
  sessionId: string | null;
  onQuery: (q: string) => void;
  onSelect: (sessionId: string) => void;
  /** The list's "+": opens WB-02 at the href it is given. */
  onNew: (href: string) => void;
}

/** A server row as the kit's row: the attribution is `formatActor`'s (INV-5). */
export function rowOf(r: SessionSummaryOut): SessionRow {
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
  };
}

export function WB01({ filter, q, sessionId, onQuery, onSelect, onNew }: WB01Props): JSX.Element {
  const list = useWorkbenchSessions({ filter, q });
  const rows = list.data?.items ?? [];
  const selected = rows.find((r) => r.id === sessionId) ?? null;
  return (
    <WorkbenchLayout
      tab="sessions"
      list={
        list.isError ? (
          <ErrorState noun="sessions" onRetry={() => void list.refetch()} />
        ) : (
          <SessionList
            rows={rows.map(rowOf)}
            selectedId={sessionId ?? undefined}
            query={q}
            onQuery={onQuery}
            onSelect={onSelect}
            onNew={() => {
              onNew(hrefOf(to.WB02()));
            }}
          />
        )
      }
      chat={
        selected?.locked === true ? (
          <RestrictedState reason="walled" title={COPY.lockedTitle} />
        ) : (
          <div data-wb01="thread" className="flex min-h-0 flex-1 flex-col" />
        )
      }
    />
  );
}
