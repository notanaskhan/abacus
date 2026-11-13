// SessionList (F-07-T02; handoff T4 LIST pane; SPEC-652 AC-2). Header 46 ("Sessions" centred, a
// round 29 px "+"), a 42 search row (SearchField and a filter button), then 48-high rows: the title
// (500 and the selected tint), the meta line from `formatActor` only ("9:21 AM · Hannah Leclerc"
// or "… via Agent"; never "Accrued Agent" as an owner, INV-5), a 12 px spinner on a running row and
// an 8 px amber dot on a row awaiting an answer. A locked row says so and opens nothing of its
// content: the host draws the restricted view (INV-3). Filtered to nothing: the filtered-empty state.
import { type JSX, useMemo, useState } from "react";
import { type Actor, formatActor } from "../../attribution/actor";
import { IconButton } from "../../components/button";
import { Menu, type MenuItem } from "../../components/popover";
import { SearchField } from "../../components/inputs";
import { Spinner } from "../../components/motion";
import { ViewStateBody } from "../../components/view-state";
import { time as clockTime } from "../../format";
import { Icon } from "../../icons";
import type { RegistryCode } from "../../status";

export type WorkbenchSessionStatus = RegistryCode<"workbench_session">;

export interface SessionRow {
  id: string;
  title: string;
  owner: Actor;
  /** ISO time of the last item. */
  last_at: string;
  state: WorkbenchSessionStatus;
  needs_answer: boolean;
  running: boolean;
  locked: boolean;
  /** W-02-T14: "Ready for review" beside the title (WB-01 a row 2). */
  ready_for_review?: boolean;
  /** W-02-T14: the server's `allowed_actions` holds `manage` (rename and delete; AC-L5). */
  manageable?: boolean;
}

export interface SessionListProps {
  rows: readonly SessionRow[];
  selectedId?: string | undefined;
  query?: string | undefined;
  /** The firm's time zone for the meta line ("America/Chicago" at Brightwater Hale). */
  timeZone?: string;
  /** Freezes motion (specimens, reduced motion). */
  still?: boolean;
  onSelect?: (id: string) => void;
  onQuery?: (q: string) => void;
  onNew?: () => void;
  onFilter?: () => void;
  /** W-02-T14: the FilterButton's menu (C2 `workbench_session_filter` words with their counts);
   * given, the filter button opens it instead of calling `onFilter`. */
  filterMenu?: MenuItem[][];
  /** W-02-T14: the filtered-empty title ("No sessions match 'K-3'."). */
  emptyTitle?: string;
  /** W-02-T14: inline rename (Pencil → field; Enter saves, Escape cancels). */
  onRename?: (id: string, title: string) => void;
  /** W-02-T14: the delete control on a manageable row (the host confirms). */
  onDelete?: (id: string) => void;
}

export const SESSION_LIST_GEOMETRY = { header: 46, search: 42, row: 48 } as const;

export function sessionMeta(row: SessionRow, timeZone = "America/Chicago"): string {
  return `${clockTime(row.last_at, { tz: timeZone })} · ${formatActor(row.owner)}`;
}

export function SessionList({
  rows,
  selectedId,
  query = "",
  timeZone = "America/Chicago",
  still = false,
  onSelect,
  onQuery,
  onNew,
  onFilter,
  filterMenu,
  emptyTitle,
  onRename,
  onDelete,
}: SessionListProps): JSX.Element {
  const g = SESSION_LIST_GEOMETRY;
  const [editing, setEditing] = useState<{ id: string; title: string } | null>(null);
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? rows.filter((r) => r.title.toLowerCase().includes(q)) : rows;
  }, [rows, query]);
  return (
    <div data-kit="SessionList" className="flex min-h-0 flex-1 flex-col">
      <header
        style={{ height: g.header }}
        className="relative flex shrink-0 items-center justify-center text-[14px] font-medium"
      >
        Sessions
        <span className="absolute right-[12px]">
          <IconButton icon="plus" label="New session" variant="dark" onClick={onNew} />
        </span>
      </header>
      <div style={{ height: g.search }} className="flex shrink-0 items-center gap-[8px] px-[12px]">
        <SearchField
          label="Search sessions"
          value={query}
          onChange={(v) => onQuery?.(v)}
          className="flex-1"
        />
        {filterMenu === undefined ? (
          <button
            type="button"
            aria-label="Filter sessions"
            onClick={onFilter}
            className="flex h-[28px] items-center gap-[2px] rounded-[7px] bg-card px-[8px] shadow-e1"
          >
            <Icon name="list-filter" size={13} />
            <Icon name="chevron-down" size={12} />
          </button>
        ) : (
          <Menu
            label="Filter sessions"
            sections={filterMenu}
            trigger={
              <button
                type="button"
                aria-label="Filter sessions"
                className="flex h-[28px] items-center gap-[2px] rounded-[7px] bg-card px-[8px] shadow-e1"
              >
                <Icon name="list-filter" size={13} />
                <Icon name="chevron-down" size={12} />
              </button>
            }
          />
        )}
      </div>
      {shown.length === 0 ? (
        <ViewStateBody
          state={{
            kind: "filtered-empty",
            query,
            ...(emptyTitle === undefined ? {} : { title: emptyTitle }),
            clear: () => onQuery?.(""),
          }}
          empty={{ title: "No sessions yet." }}
          noun="sessions"
        >
          {null}
        </ViewStateBody>
      ) : (
        <ul aria-label="Sessions" className="min-h-0 flex-1 overflow-y-auto">
          {shown.map((row) => {
            const selected = row.id === selectedId;
            if (editing?.id === row.id) {
              return (
                <li key={row.id} style={{ height: g.row }} className="flex items-center px-[12px]">
                  <input
                    aria-label="Session title"
                    autoFocus
                    value={editing.title}
                    maxLength={120}
                    onChange={(e) => setEditing({ id: row.id, title: e.target.value })}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && editing.title.trim() !== "") {
                        onRename?.(row.id, editing.title.trim());
                        setEditing(null);
                      } else if (e.key === "Escape") {
                        setEditing(null);
                      }
                    }}
                    onBlur={() => setEditing(null)}
                    className="h-[28px] w-full rounded-[6px] border border-line bg-card px-[6px] text-[13px]"
                  />
                </li>
              );
            }
            const manage = row.manageable === true && !row.locked;
            return (
              <li key={row.id} className="group relative">
                <button
                  type="button"
                  data-session={row.id}
                  data-selected={selected}
                  data-locked={row.locked}
                  aria-current={selected ? "true" : undefined}
                  onClick={() => onSelect?.(row.id)}
                  style={{ height: g.row }}
                  className={`flex w-full items-center gap-[8px] border-b border-hair px-[12px] text-left ${
                    selected ? "bg-sel-bg" : ""
                  }`}
                >
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className={`truncate text-[13px] ${selected ? "font-medium" : ""}`}>
                      {row.title}
                    </span>
                    <span data-meta className="truncate text-[11.5px] text-ink-3">
                      {sessionMeta(row, timeZone)}
                      {row.locked ? " · Locked" : ""}
                    </span>
                  </span>
                  {row.running ? (
                    <Spinner label="Running" size={10} showLabel={false} still={still} />
                  ) : row.needs_answer ? (
                    <span
                      role="img"
                      aria-label="Awaiting your answer"
                      data-awaiting
                      className="block size-[8px] rounded-pill bg-amber"
                    />
                  ) : row.ready_for_review === true ? (
                    <span data-ready className="shrink-0 text-[11px] text-green-ink">
                      Ready for review
                    </span>
                  ) : null}
                </button>
                {manage && (onRename !== undefined || onDelete !== undefined) ? (
                  <span className="absolute right-[8px] top-[10px] hidden gap-[2px] group-focus-within:flex group-hover:flex">
                    {onRename === undefined ? null : (
                      <IconButton
                        icon="pencil"
                        label="Rename session"
                        onClick={() => setEditing({ id: row.id, title: row.title })}
                      />
                    )}
                    {onDelete === undefined ? null : (
                      <IconButton icon="trash-2" label="Delete session" onClick={() => onDelete(row.id)} />
                    )}
                  </span>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
