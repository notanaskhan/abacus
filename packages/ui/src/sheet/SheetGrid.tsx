import { Lock, MoreHorizontal } from "lucide-react";
import { type JSX, useMemo, useRef, useState } from "react";
import { cn } from "../cn";
import { useRowWindow } from "../data/row-window";
import { COLUMN_GLYPHS } from "./glyphs";
import type {
  SheetGridColumn,
  SheetColumnIntent,
  SheetGridProps,
  SheetGridRow,
  SheetSection,
} from "./types";

// T18 SheetGrid core (F-08-T05; F-08 A1; chapter 03 §3.6). A grid that reads like a workpaper:
// 11 typed columns with Lucide glyph headers and a "···" menu that only emits intents; the 28 px
// select column and the 96 px Geist Mono Key column frozen during horizontal scroll; hairline
// grid; rows ≥ 34 px; the dark SectionBand (31) and the light sub-band (28) with the server's
// total; an optional filter row; the 30 px status bar. Virtualised from 200 items (E4,
// row-window.ts) with `aria-rowcount` / `aria-rowindex` kept exact.
//
// Never: column letters, row numbers, zebra rows, coloured headers, blue or green selection,
// "$" in a cell, a sum computed here (ADR-050). Editing and locks are F-08-T06; agent-cell states
// and their citations F-08-T07; the toolbar, drawer and sign-off slots ride SheetLayout (T08).

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
    ...(column.type === "agent"
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
}: SheetGridProps): JSX.Element {
  const scroller = useRef<HTMLDivElement | null>(null);
  const list = useMemo(() => items(sections, rows), [sections, rows]);
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
                  {columns.map((c) => {
                    const cell = row.cells[c.key];
                    const left = frozenLeft(columns, c.key);
                    const isKey = c.frozen === true && left === SELECT_W;
                    return (
                      <td
                        key={c.key}
                        role="gridcell"
                        data-state={cell?.state ?? "empty"}
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
                        <span className="line-clamp-3 flex items-start gap-[4px]">
                          {isKey && row.locked && (
                            <Lock
                              aria-label="Locked"
                              className="mt-[1px] size-[11px] shrink-0 text-ink-3"
                            />
                          )}
                          {cell?.value ?? ""}
                        </span>
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
      <div
        role="status"
        className="flex h-[30px] items-center gap-[12px] border-t border-hair bg-band-hd px-[10px] text-meta text-ink-3"
      >
        <span>{`${String(status.rows)} rows · ${String(status.exceptions)} exception${status.exceptions === 1 ? "" : "s"} · View: ${status.view}`}</span>
        {status.agentRunning === true && <span className="text-ink-2">Agent column running</span>}
      </div>
    </div>
  );
}
