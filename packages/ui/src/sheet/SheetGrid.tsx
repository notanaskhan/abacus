import { Lock, MoreHorizontal } from "lucide-react";
import {
  type ClipboardEvent,
  type JSX,
  type KeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { cn } from "../cn";
import { ErrorRow } from "../components/states";
import { useRowWindow } from "../data/row-window";
import { AgentFilledCell } from "./AgentFilledCell";
import { COLUMN_GLYPHS } from "./glyphs";
import type {
  AgentUnavailable,
  SheetCellEdit,
  SheetColumnIntent,
  SheetEditConflict,
  SheetGridColumn,
  SheetGridProps,
  SheetGridRow,
  SheetRunSource,
  SheetRunState,
  SheetSection,
} from "./types";

/** F-08-T07: the DF-04 reasons on the agent column header, verbatim (F-08 §6; SHL-23 copy). */
export const AGENT_UNAVAILABLE: Record<AgentUnavailable, string> = {
  real_client_data: "AI isn't available for real client data yet",
  consent_7216: "Agents are off for this taxpayer — §7216 consent isn't on file",
};

const IDLE: SheetRunState = { running: false };
const NO_RUN: SheetRunSource = {
  subscribe: () => () => undefined,
  getSnapshot: () => IDLE,
};

/** T18g's tooltip, verbatim (handoff T18 spec, States). */
export const LOCKED_TOOLTIP =
  "Signed-off rows are locked. Sign-offs are removed only from the sign-off modal.";
// F-08-T06: the types a person edits here; linked, sign-off and agent cells never are.
const EDITABLE: ReadonlySet<string> = new Set([
  "text",
  "number",
  "currency",
  "date",
  "single_select",
  "person",
]);
const PAGE = 10;

function editable(column: SheetGridColumn): boolean {
  return EDITABLE.has(column.type) && column.frozen !== true;
}

function conflictOf(raised: unknown): SheetEditConflict | null {
  if (typeof raised !== "object" || raised === null) return null;
  const status = (raised as { status?: unknown }).status;
  if (status !== 409 && status !== 412) return null;
  const by = (raised as { changedBy?: unknown }).changedBy;
  return typeof by === "string" ? { status, changedBy: by } : { status };
}

// T18 SheetGrid core (F-08-T05; F-08 A1; chapter 03 §3.6). A grid that reads like a workpaper:
// 11 typed columns with Lucide glyph headers and a "···" menu that only emits intents; the 28 px
// select column and the 96 px Geist Mono Key column frozen during horizontal scroll; hairline
// grid; rows ≥ 34 px; the dark SectionBand (31) and the light sub-band (28) with the server's
// total; an optional filter row; the 30 px status bar. Virtualised from 200 items (E4,
// row-window.ts) with `aria-rowcount` / `aria-rowindex` kept exact.
//
// Never: column letters, row numbers, zebra rows, coloured headers, blue or green selection,
// "$" in a cell, a sum computed here (ADR-050). F-08-T06: typed editors (Enter or F2 to edit, Esc
// to cancel, Tab or Enter to commit through onCellEdit with the row's version), a roving focus
// under role="grid" (arrows, Home/End, PageUp/PageDown, edit mode announced) and locked rows that
// refuse typing, paste, Delete and Backspace with T18g's tooltip; a 409/412 rejection shows the
// C-20 ErrorRow "Changed by <name> — reload". Agent-cell states and their citations are F-08-T07;
// the toolbar, drawer and sign-off slots ride SheetLayout (T08).

const SELECT_W = 28;
const HEIGHTS = { band: 31, sub: 28, row: 34 } as const;

type Item =
  { kind: "band"; section: SheetSection } | { kind: "row"; row: SheetGridRow; index: number };

function items(sections: readonly SheetSection[], rows: readonly SheetGridRow[]): Item[] {
  const out: Item[] = [];
  let index = 0;
  for (const section of sections) {
    out.push({ kind: "band", section });
    for (const row of rows) {
      if (row.sectionKey === section.key) out.push({ kind: "row", row, index: index++ });
    }
  }
  return out;
}

function sizeOf(item: Item): number {
  if (item.kind === "row") return HEIGHTS.row;
  return item.section.sub === true ? HEIGHTS.sub : HEIGHTS.band;
}

function frozenLeft(columns: readonly SheetGridColumn[], key: string): number | undefined {
  let left = SELECT_W;
  for (const c of columns) {
    if (c.frozen !== true) continue;
    if (c.key === key) return left;
    left += c.width;
  }
  return undefined;
}

function HeaderCell({
  column,
  left,
  onIntent,
}: {
  column: SheetGridColumn;
  left: number | undefined;
  onIntent: ((columnKey: string, intent: SheetColumnIntent) => void) | undefined;
}): JSX.Element {
  const Glyph = COLUMN_GLYPHS[column.type];
  const [open, setOpen] = useState(false);
  const intents: { label: string; intent: SheetColumnIntent }[] = [
    { label: "Sort ascending", intent: { kind: "sort", dir: "asc" } },
    { label: "Sort descending", intent: { kind: "sort", dir: "desc" } },
    { label: "Filter", intent: { kind: "filter" } },
    { label: "Hide column", intent: { kind: "hide" } },
    ...(column.type === "agent" && column.agent?.unavailable === undefined
      ? [
          { label: "Edit agent column…", intent: { kind: "edit_agent_column" } as const },
          { label: "Run on empty rows", intent: { kind: "run_on_empty_rows" } as const },
        ]
      : []),
  ];
  return (
    <th
      role="columnheader"
      scope="col"
      data-column-type={column.type}
      style={{ width: column.width, minWidth: column.width, left }}
      className={cn(
        "relative h-[32px] border-b border-r border-hair bg-band-hd px-[8px] text-left text-th font-normal text-ink-2",
        left !== undefined && "sticky z-[2]",
      )}
    >
      <span className="flex items-center gap-[6px]">
        <Glyph aria-hidden className="size-[12px] shrink-0 text-ink-3" />
        <span className="truncate">{column.label}</span>
        {column.agent?.unavailable !== undefined && (
          <span className="truncate text-meta text-ink-3" data-agent-unavailable="">
            {AGENT_UNAVAILABLE[column.agent.unavailable]}
          </span>
        )}
        <button
          type="button"
          aria-label={`${column.label} column menu`}
          aria-haspopup="menu"
          aria-expanded={open}
          className="ml-auto rounded-[4px] px-[2px] text-ink-3 hover:bg-chip"
          onClick={() => {
            setOpen((v) => !v);
          }}
        >
          <MoreHorizontal aria-hidden className="size-[12px]" />
        </button>
      </span>
      {open && (
        <ul
          role="menu"
          className="absolute right-[4px] top-[30px] z-[5] min-w-[180px] rounded-[8px] border border-hair bg-card py-[4px] text-dense text-ink"
        >
          {intents.map((i) => (
            <li key={i.label} role="none">
              <button
                type="button"
                role="menuitem"
                className="w-full px-[10px] py-[6px] text-left hover:bg-nested"
                onClick={() => {
                  setOpen(false);
                  onIntent?.(column.key, i.intent);
                }}
              >
                {i.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </th>
  );
}

export function SheetGrid({
  columns,
  sections,
  rows,
  status,
  label,
  selected,
  onSelect,
  onColumnIntent,
  filterRow = false,
  height = 560,
  onCellEdit,
  viewer,
  onAdopt,
  onEditAgentValue,
  onOpenRow,
  run = NO_RUN,
}: SheetGridProps): JSX.Element {
  const runState = useSyncExternalStore(run.subscribe, run.getSnapshot, run.getSnapshot);
  const agentRunning = runState.running || status.agentRunning === true;
  const scroller = useRef<HTMLDivElement | null>(null);
  const table = useRef<HTMLTableElement | null>(null);
  const list = useMemo(() => items(sections, rows), [sections, rows]);
  const ordered = useMemo(() => list.flatMap((i) => (i.kind === "row" ? [i.row] : [])), [list]);
  const [active, setActive] = useState({ row: 0, col: 0 });
  const [editing, setEditing] = useState<{ rowKey: string; colKey: string; draft: string } | null>(
    null,
  );
  const [conflict, setConflict] = useState<{ rowKey: string; by: string } | null>(null);
  const [announce, setAnnounce] = useState("");
  const moved = useRef(false);
  useEffect(() => {
    if (!moved.current) return;
    moved.current = false;
    const r = ordered[active.row];
    const c = columns[active.col];
    if (r === undefined || c === undefined) return;
    table.current
      ?.querySelector<HTMLElement>(`[data-row-key="${r.key}"] [data-col-key="${c.key}"]`)
      ?.focus();
  }, [active, ordered, columns]);

  function moveTo(row: number, col: number): void {
    moved.current = true;
    setActive({
      row: Math.max(0, Math.min(ordered.length - 1, row)),
      col: Math.max(0, Math.min(columns.length - 1, col)),
    });
  }

  function refuse(): void {
    setAnnounce(LOCKED_TOOLTIP);
  }

  async function commit(edit: SheetCellEdit, next?: { row: number; col: number }): Promise<void> {
    setEditing(null);
    if (next !== undefined) moveTo(next.row, next.col);
    else moved.current = true;
    if (onCellEdit === undefined) return;
    try {
      await onCellEdit(edit);
      setConflict(null);
    } catch (raised: unknown) {
      const found = conflictOf(raised);
      if (found === null) throw raised;
      setConflict({ rowKey: edit.rowKey, by: found.changedBy ?? "someone" });
    }
  }

  function onCellKey(
    e: KeyboardEvent<HTMLElement>,
    row: SheetGridRow,
    rowAt: number,
    column: SheetGridColumn,
    colAt: number,
  ): void {
    if (editing !== null) return;
    const canEdit = editable(column);
    switch (e.key) {
      case "ArrowRight":
        e.preventDefault();
        moveTo(rowAt, colAt + 1);
        return;
      case "ArrowLeft":
        e.preventDefault();
        moveTo(rowAt, colAt - 1);
        return;
      case "ArrowDown":
        e.preventDefault();
        moveTo(rowAt + 1, colAt);
        return;
      case "ArrowUp":
        e.preventDefault();
        moveTo(rowAt - 1, colAt);
        return;
      case "Home":
        e.preventDefault();
        moveTo(rowAt, 0);
        return;
      case "End":
        e.preventDefault();
        moveTo(rowAt, columns.length - 1);
        return;
      case "PageDown":
        e.preventDefault();
        moveTo(rowAt + PAGE, colAt);
        return;
      case "PageUp":
        e.preventDefault();
        moveTo(rowAt - PAGE, colAt);
        return;
      default:
        break;
    }
    // Fill down (Ctrl/Cmd+D): the cell takes the value of the cell above it, as one edit.
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "d" && canEdit) {
      e.preventDefault();
      if (row.locked) {
        refuse();
        return;
      }
      const above = ordered[rowAt - 1]?.cells[column.key];
      if (above === undefined) return;
      void commit({
        rowKey: row.key,
        colKey: column.key,
        value: above.raw ?? above.value,
        version: row.version,
      });
      return;
    }
    const typing = e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey;
    const wants = e.key === "Enter" || e.key === "F2" || e.key === "Delete" ||
      e.key === "Backspace" || typing; // prettier-ignore
    if (!wants || !canEdit) return;
    e.preventDefault();
    if (row.locked) {
      refuse();
      return;
    }
    if (e.key === "Delete" || e.key === "Backspace") {
      void commit({ rowKey: row.key, colKey: column.key, value: "", version: row.version });
      return;
    }
    const cell = row.cells[column.key];
    const start = typing ? e.key : (cell?.raw ?? cell?.value ?? "");
    setEditing({ rowKey: row.key, colKey: column.key, draft: start });
    setAnnounce(`Editing ${column.label}`);
  }

  function onCellPaste(e: ClipboardEvent<HTMLElement>, row: SheetGridRow): void {
    if (!row.locked) return;
    e.preventDefault();
    refuse();
  }
  const rowWindow = useRowWindow({
    count: list.length,
    size: (i) => {
      const item = list[i];
      return item === undefined ? HEIGHTS.row : sizeOf(item);
    },
    scroller,
    height,
  });
  // Header row(s) count toward aria-rowcount: the column header, then the filter row.
  const headRows = filterRow ? 2 : 1;
  const span = columns.length + 1;

  return (
    <div className="flex flex-col border border-hair bg-card">
      <div
        ref={scroller}
        className="overflow-auto"
        style={{ maxHeight: rowWindow.virtual ? height : undefined }}
      >
        <table
          ref={table}
          role="grid"
          aria-label={label}
          aria-rowcount={list.length + headRows}
          className="border-separate border-spacing-0 text-cell text-ink"
        >
          <thead className="sticky top-0 z-[3]">
            <tr role="row" aria-rowindex={1}>
              <th
                role="columnheader"
                aria-label="Select"
                style={{ width: SELECT_W, minWidth: SELECT_W, left: 0 }}
                className="sticky z-[2] h-[32px] border-b border-r border-hair bg-band-hd"
              />
              {columns.map((c) => (
                <HeaderCell
                  key={c.key}
                  column={c}
                  left={frozenLeft(columns, c.key)}
                  onIntent={onColumnIntent}
                />
              ))}
            </tr>
            {filterRow && (
              <tr role="row" aria-rowindex={2} data-filter-row="">
                <td
                  style={{ left: 0 }}
                  className="sticky z-[2] h-[30px] border-b border-r border-hair bg-card"
                />
                {columns.map((c) => (
                  <td
                    key={c.key}
                    style={{ left: frozenLeft(columns, c.key) }}
                    className={cn(
                      "h-[30px] border-b border-r border-hair bg-card px-[6px]",
                      frozenLeft(columns, c.key) !== undefined && "sticky z-[2]",
                    )}
                  >
                    <input
                      aria-label={`Filter ${c.label}`}
                      className="h-[22px] w-full rounded-[4px] border border-hair px-[6px] text-cell"
                    />
                  </td>
                ))}
              </tr>
            )}
          </thead>
          <tbody>
            {rowWindow.before > 0 && (
              <tr aria-hidden style={{ height: rowWindow.before }}>
                <td colSpan={span} />
              </tr>
            )}
            {rowWindow.indexes.map((i) => {
              const item = list[i];
              if (item === undefined) return null;
              const rowIndex = i + headRows + 1;
              if (item.kind === "band") {
                const sub = item.section.sub === true;
                return (
                  <tr
                    key={`band-${item.section.key}`}
                    role="row"
                    aria-rowindex={rowIndex}
                    data-band={sub ? "sub" : "section"}
                  >
                    <td
                      colSpan={span}
                      style={{ height: sub ? HEIGHTS.sub : HEIGHTS.band }}
                      className={cn(
                        "px-[10px]",
                        sub
                          ? "bg-sel-bg text-th text-ink-2"
                          : "bg-espresso text-band-dark text-on-dark",
                      )}
                    >
                      <span className="flex items-center justify-between">
                        <span>{`${sub ? item.section.title : item.section.title.toUpperCase()} (${String(item.section.count)})`}</span>
                        {item.section.total !== undefined && (
                          <span className="tabular-nums">{item.section.total}</span>
                        )}
                      </span>
                    </td>
                  </tr>
                );
              }
              const { row } = item;
              const on = selected?.has(row.key) ?? false;
              return (
                <tr
                  key={row.key}
                  role="row"
                  aria-rowindex={rowIndex}
                  aria-selected={on}
                  data-row-key={row.key}
                  data-locked={row.locked ? "" : undefined}
                  className={cn(on && "bg-sel-bg")}
                >
                  <td
                    role="gridcell"
                    style={{ left: 0 }}
                    className="sticky z-[1] h-[34px] border-b border-r border-hair bg-inherit px-[7px]"
                  >
                    <input
                      type="checkbox"
                      aria-label={`Select ${row.key}`}
                      checked={on}
                      onChange={(e) => onSelect?.(row.key, e.target.checked)}
                    />
                  </td>
                  {columns.map((c, colAt) => {
                    const cell = row.cells[c.key];
                    const left = frozenLeft(columns, c.key);
                    const isKey = c.frozen === true && left === SELECT_W;
                    const rowAt = ordered.indexOf(row);
                    const here = active.row === rowAt && active.col === colAt;
                    const open = editing?.rowKey === row.key && editing.colKey === c.key;
                    return (
                      <td
                        key={c.key}
                        role="gridcell"
                        data-col-key={c.key}
                        data-state={cell?.state ?? "empty"}
                        tabIndex={here ? 0 : -1}
                        aria-readonly={row.locked || !editable(c) ? "true" : undefined}
                        title={row.locked ? LOCKED_TOOLTIP : undefined}
                        onFocus={() => {
                          if (!here) setActive({ row: rowAt, col: colAt });
                        }}
                        onKeyDown={(e) => {
                          onCellKey(e, row, rowAt, c, colAt);
                        }}
                        onPaste={(e) => {
                          onCellPaste(e, row);
                        }}
                        style={{ width: c.width, minWidth: c.width, left }}
                        className={cn(
                          "border-b border-r border-hair px-[8px] py-[8px] align-top",
                          left !== undefined && "sticky z-[1] bg-card",
                          isKey && "font-mono",
                          (c.type === "number" || c.type === "currency") &&
                            "text-right tabular-nums",
                          cell?.state === "suggested" && "text-ink-2",
                        )}
                      >
                        {open ? (
                          <CellEditor
                            column={c}
                            draft={editing.draft}
                            onDraft={(draft) => {
                              setEditing({ rowKey: row.key, colKey: c.key, draft });
                            }}
                            onCancel={() => {
                              setEditing(null);
                              setAnnounce("");
                              moved.current = true;
                              setActive({ row: rowAt, col: colAt });
                            }}
                            onCommit={(value, how) => {
                              void commit(
                                { rowKey: row.key, colKey: c.key, value, version: row.version },
                                how === "tab"
                                  ? { row: rowAt, col: colAt + 1 }
                                  : { row: rowAt, col: colAt },
                              );
                            }}
                          />
                        ) : c.type === "agent" ? (
                          <AgentFilledCell
                            value={cell?.value ?? ""}
                            state={agentState(cell?.state)}
                            citations={cell?.citations}
                            by={cell?.by}
                            at={cell?.at}
                            was={cell?.was}
                            exception={cell?.exception}
                            running={
                              runState.running &&
                              (runState.pendingRowKeys === undefined ||
                                runState.pendingRowKeys.has(row.key))
                            }
                            viewer={viewer ?? { kind: "system" }}
                            onAdopt={
                              onAdopt === undefined ? undefined : () => onAdopt(row.key, c.key)
                            }
                            onEdit={
                              onEditAgentValue === undefined
                                ? undefined
                                : () => {
                                    onEditAgentValue(row.key, c.key);
                                  }
                            }
                            onOpenRow={
                              onOpenRow === undefined
                                ? undefined
                                : () => {
                                    onOpenRow(row.key);
                                  }
                            }
                          />
                        ) : (
                          <span className="line-clamp-3 flex items-start gap-[4px]">
                            {isKey && row.locked && (
                              <Lock
                                aria-label="Locked"
                                className="mt-[1px] size-[11px] shrink-0 text-ink-3"
                              />
                            )}
                            {cell?.value ?? ""}
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
            {rowWindow.after > 0 && (
              <tr aria-hidden style={{ height: rowWindow.after }}>
                <td colSpan={span} />
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {conflict !== null && (
        <ErrorRow title={`Changed by ${conflict.by} — reload`} className="border-t border-hair" />
      )}
      <p
        aria-live="polite"
        aria-atomic="true"
        data-testid="sheet-announcements"
        className="sr-only"
      >
        {announce}
      </p>
      <div
        role="status"
        className="flex h-[30px] items-center gap-[12px] border-t border-hair bg-band-hd px-[10px] text-meta text-ink-3"
      >
        <span>{`${String(status.rows)} rows · ${String(status.exceptions)} exception${status.exceptions === 1 ? "" : "s"} · View: ${status.view}`}</span>
        {agentRunning && <span className="text-ink-2">Agent column running</span>}
      </div>
    </div>
  );
}

function CellEditor({
  column,
  draft,
  onDraft,
  onCancel,
  onCommit,
}: {
  column: SheetGridColumn;
  draft: string;
  onDraft: (draft: string) => void;
  onCancel: () => void;
  onCommit: (value: string, how: "enter" | "tab") => void;
}): JSX.Element {
  const ref = useRef<HTMLInputElement | HTMLSelectElement | null>(null);
  useEffect(() => {
    ref.current?.focus();
  }, []);
  function keys(e: KeyboardEvent<HTMLElement>): void {
    if (e.key === "Escape") {
      e.preventDefault();
      onCancel();
    } else if (e.key === "Enter" || e.key === "Tab") {
      e.preventDefault();
      onCommit(draft, e.key === "Tab" ? "tab" : "enter");
    }
  }
  const frame =
    "h-[22px] w-full rounded-[4px] border border-hair bg-card px-[6px] text-cell text-ink";
  if (column.type === "single_select" || column.type === "person") {
    return (
      <select
        ref={(el) => {
          ref.current = el;
        }}
        aria-label={column.label}
        className={frame}
        value={column.options?.find((o) => o.label === draft)?.value ?? draft}
        onKeyDown={keys}
        onChange={(e) => {
          onCommit(e.target.value, "enter");
        }}
      >
        {(column.options ?? []).map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    );
  }
  return (
    <input
      ref={(el) => {
        ref.current = el;
      }}
      aria-label={column.label}
      type={column.type === "date" ? "date" : "text"}
      inputMode={column.type === "number" || column.type === "currency" ? "decimal" : undefined}
      className={cn(
        frame,
        (column.type === "number" || column.type === "currency") && "text-right",
      )}
      value={draft}
      onKeyDown={keys}
      onChange={(e) => {
        onDraft(e.target.value);
      }}
    />
  );
}

/** An agent cell's state: a human value in an agent column reads as adopted. */
function agentState(
  state: SheetGridRow["cells"][string]["state"] | undefined,
): "empty" | "suggested" | "adopted" | "edited" {
  if (state === undefined || state === "empty") return "empty";
  return state === "human" ? "adopted" : state;
}
