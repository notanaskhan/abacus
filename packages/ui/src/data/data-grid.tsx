import { tableFeatures, useTable } from "@tanstack/react-table";
import { type JSX, type KeyboardEvent, useId, useMemo, useRef, useState } from "react";
import { cn } from "../cn";
import type { MatchId } from "../tracing/types";
import { MoneyCell, PropChip, TickCell, ValueChip } from "./cells";
import type { ColumnType, Grammar, TableColumn, TableRow } from "./types";
import { MatchCell, MatchRow } from "./match-cells";
import { VIRTUAL_HEIGHT, useRowWindow } from "./row-window";
import { NoteCorner, VarianceAction, VarianceCell, varianceState } from "./variance";

// E4 DataTable engine (F-05-T27; plan 04 E4; C-01 spec 01 to 03 and 06): one headless model on
// @tanstack/react-table and a renderer per grammar: `ledger` (closes and reconciliations: 30px
// rows, 12.5px, "$" with cents), `statement` (financial statements: th 30, td 26, whole dollars,
// uppercase group bands) and `evidence` (audit workpapers: th 28, td 29, 12px, "$" with cents,
// a fixed layout, extracted-value chips; its blocks sit on a well, evidence.tsx). A `variance`
// column draws the VarianceCell and gains the 100px action column (F-05-T43). `leadsheet` (tax
// worksheets and leadsheets: no column header, the block title heads it; rows padding 9 14 at
// 13px, whole dollars, an optional 52px line-number column, totals 500 over the .22 rule) joins
// in F-05-T52, with the grid grammar's own markup in grid.tsx.
//
// - Above 200 rows the table virtualises (row-window.ts) inside its own scroll viewport, and its
//   header and group bands stay sticky. `aria-rowindex` keeps every row's place.
//
// - Grid semantics: `role="grid"`, one focusable container, ↑/↓ move the selection (clamped),
//   Home/End jump, Enter (or a double click) opens. Keys are ignored while an input, button or
//   link inside has focus.
// - Totals are rows from the server. No code path here sums a column (ADR-050).
// - No zebra rows; numbers are never truncated.

const FEATURES = tableFeatures({});

interface GrammarMetrics {
  /** Body type role. */
  text: string;
  /** False: no visible column header (the leadsheet's block title is its header). */
  header: boolean;
  /** Exact heights, for the virtualiser: a header cell, an item row and a group band. */
  heights: { th: number; td: number; group: number };
  layout: "auto" | "fixed";
  th: string;
  td: string;
  pad: number;
  indentStep: number;
  format: "money" | "whole";
  group: string;
  total: string;
  numTracking: string;
}

const GRAMMARS: Record<Grammar, GrammarMetrics> = {
  ledger: {
    text: "text-dense",
    header: true,
    heights: { th: 30, td: 30, group: 31 },
    layout: "auto",
    th: "h-[30px] bg-band-hd text-dense font-normal text-ink-2",
    td: "h-[30px]",
    pad: 12,
    indentStep: 18,
    format: "money",
    group: "h-[31px] bg-band-hd text-body font-normal text-ink-2",
    total: "bg-band-hd font-medium",
    numTracking: "tracking-[-0.01em]",
  },
  statement: {
    text: "text-cell",
    header: true,
    heights: { th: 30, td: 26, group: 24 },
    layout: "auto",
    th: "h-[30px] bg-band-hd text-th font-medium text-ink-3",
    td: "h-[26px]",
    pad: 10,
    indentStep: 25,
    format: "whole",
    group: "h-[24px] bg-band-hd text-group-row font-medium tracking-[0.07em] uppercase text-ink-3",
    total: "font-medium",
    numTracking: "tracking-[-0.005em]",
  },
  evidence: {
    text: "text-cell",
    header: true,
    heights: { th: 28, td: 29, group: 29 },
    layout: "fixed",
    th: "h-[28px] bg-band-hd text-meta font-normal text-ink-2 border-y-[0.5px] border-hair",
    td: "h-[29px]",
    pad: 12,
    indentStep: 16,
    format: "money",
    group: "h-[29px] text-cell font-medium text-ink",
    total: "font-medium",
    numTracking: "tracking-[-0.005em]",
  },
  leadsheet: {
    text: "text-body",
    header: false,
    heights: { th: 0, td: 37, group: 37 },
    layout: "auto",
    th: "text-meta font-normal",
    td: "py-[9px] leading-[1.45]",
    pad: 14,
    indentStep: 16,
    format: "whole",
    group: "bg-band-hd py-[9px] text-body leading-[1.45] font-normal text-ink-2",
    total: "font-medium",
    numTracking: "tracking-[-0.005em]",
  },
};

/** The action column a variance column brings (C-01 spec 06): 100 wide, right-aligned. */
const ACTION_WIDTH = 100;

function typeOf(column: TableColumn, index: number): ColumnType {
  return column.type ?? (index === 0 ? "label" : "num");
}

function rightAligned(column: TableColumn, type: ColumnType): boolean {
  return (column.align ?? (type === "num" || type === "variance" ? "right" : "left")) === "right";
}

export interface DataGridProps {
  /** The accessible name of the grid. */
  label: string;
  grammar?: Grammar;
  columns: readonly TableColumn[];
  rows: readonly TableRow[];
  /** The selected row (controlled); omit to let the grid hold it. */
  selected?: string | null;
  onSelect?: (id: string, row: TableRow) => void;
  /** Enter or a double click. */
  onOpen?: (row: TableRow) => void;
  /** "Explain…" on an unexplained variance: the screen opens its editor. */
  onExplain?: (row: TableRow, columnKey: string) => void;
  /** The issue link on a variance exception. */
  onIssue?: (row: TableRow) => void;
  /** Overrides the grammar's side padding (a workpaper's evidence table is pad 14, C-02). */
  pad?: number;
  /** A cell's match id, from its typed locator (INV-2): the cell lights as the exact cell and its
   * row as the row whenever that match is the scope's active one (F-05-T50). */
  cellMatch?: (row: TableRow, columnKey: string) => MatchId | undefined;
  /** A row's own match (a leadsheet line matched to the open document): the whole row lights. */
  rowMatch?: (row: TableRow) => MatchId | undefined;
  /** Default: virtualise at 200 rows and above. */
  virtualize?: boolean;
  /** The scroll viewport's height when virtualised, px. */
  maxHeight?: number;
  className?: string;
}

export function DataGrid({
  label,
  grammar = "ledger",
  columns,
  rows,
  selected,
  onSelect,
  onOpen,
  onExplain,
  onIssue,
  pad: padOverride,
  cellMatch,
  rowMatch,
  virtualize,
  maxHeight = VIRTUAL_HEIGHT,
  className,
}: DataGridProps): JSX.Element {
  const g = { ...GRAMMARS[grammar], ...(padOverride === undefined ? {} : { pad: padOverride }) };
  const varianceKey = columns.find((c) => c.type === "variance")?.key;
  const gridId = useId();
  const columnDefs = useMemo(
    () =>
      columns.map((c) => ({
        id: c.key,
        header: c.header,
        accessorFn: (row: TableRow) => row.cells[c.key]?.value ?? null,
      })),
    [columns],
  );
  const table = useTable({
    features: FEATURES,
    columns: columnDefs,
    data: rows,
    getRowId: (row: TableRow) => row.id,
  });
  const model = table.getRowModel().rows.map((r) => r.original);
  const [own, setOwn] = useState<string | null>(null);
  const current = selected === undefined ? own : selected;
  // Group bands are headings, not stops: selection moves over items and totals.
  const stops = model.filter((r) => (r.kind ?? "item") !== "group");
  const scroller = useRef<HTMLDivElement>(null);
  const win = useRowWindow({
    count: model.length,
    size: (i) => ((model[i]?.kind ?? "item") === "group" ? g.heights.group : g.heights.td),
    scroller,
    enabled: virtualize,
    height: maxHeight,
  });

  function select(row: TableRow): void {
    if (selected === undefined) setOwn(row.id);
    onSelect?.(row.id, row);
    if (win.virtual) {
      win.scrollTo(model.indexOf(row));
      return;
    }
    // Optional: jsdom has no scrollIntoView.
    const el = document.getElementById(`${gridId}-${row.id}`) as Partial<HTMLElement> | null;
    el?.scrollIntoView?.({ block: "nearest" });
  }

  function onKeyDown(event: KeyboardEvent<HTMLTableElement>): void {
    const target = event.target as HTMLElement;
    if (target !== event.currentTarget && target.closest("input, textarea, button, a, select")) {
      return;
    }
    if (stops.length === 0) return;
    const at = stops.findIndex((r) => r.id === current);
    const move = (to: number): void => {
      event.preventDefault();
      const row = stops[Math.max(0, Math.min(stops.length - 1, to))];
      if (row !== undefined) select(row);
    };
    switch (event.key) {
      case "ArrowDown":
        move(at < 0 ? 0 : at + 1);
        break;
      case "ArrowUp":
        move(at < 0 ? 0 : at - 1);
        break;
      case "Home":
        move(0);
        break;
      case "End":
        move(stops.length - 1);
        break;
      case "Enter": {
        const row = stops[at];
        if (row !== undefined) {
          event.preventDefault();
          onOpen?.(row);
        }
        break;
      }
      default:
    }
  }

  const pad = { paddingLeft: g.pad, paddingRight: g.pad };
  const span = columns.length + (varianceKey === undefined ? 0 : 1);
  const sticky = win.virtual;
  const grid = (
    <table
      role="grid"
      aria-label={label}
      aria-rowcount={model.length + 1}
      aria-activedescendant={current === null ? undefined : `${gridId}-${current}`}
      tabIndex={0}
      data-grammar={grammar}
      onKeyDown={onKeyDown}
      className={cn(
        "w-full border-collapse tracking-[-0.005em] focus-visible:outline-offset-[-2px]",
        g.layout === "fixed" && "table-fixed",
        // No header: the first row draws no rule above it.
        !g.header && "[&>tbody>tr:first-child>td]:border-t-0",
        g.text,
        !win.virtual && className,
      )}
    >
      <thead className={cn(!g.header && "sr-only")}>
        <tr role="row" aria-rowindex={1}>
          {columns.map((c, i) => {
            const type = typeOf(c, i);
            return (
              <th
                key={c.key}
                role="columnheader"
                scope="col"
                style={{ ...pad, width: c.width, paddingRight: c.tick === true ? 62 : g.pad }}
                className={cn(
                  "truncate whitespace-nowrap",
                  sticky && "sticky top-0 z-[2]",
                  g.th,
                  c.entity === true && "text-body font-medium text-ink",
                  rightAligned(c, type) ? "text-right" : "text-left",
                )}
              >
                {c.header}
              </th>
            );
          })}
          {varianceKey !== undefined && (
            <th
              role="columnheader"
              scope="col"
              style={{ width: ACTION_WIDTH, paddingLeft: g.pad, paddingRight: g.pad }}
              className={cn("text-right", sticky && "sticky top-0 z-[2]", g.th)}
            >
              <span className="sr-only">Action</span>
            </th>
          )}
        </tr>
      </thead>
      <tbody>
        {win.before > 0 && (
          <tr aria-hidden="true" style={{ height: win.before }}>
            <td colSpan={span} className="p-0" />
          </tr>
        )}
        {win.indexes.map((index) => {
          const row = model[index];
          if (row === undefined) return null;
          const kind = row.kind ?? "item";
          const isSelected = row.id === current;
          const rowIndex = index + 2;
          if (kind === "group") {
            return (
              <tr
                key={row.id}
                id={`${gridId}-${row.id}`}
                role="row"
                aria-rowindex={rowIndex}
                data-index={index}
              >
                <th
                  role="rowheader"
                  scope="rowgroup"
                  colSpan={span}
                  style={{ ...pad, ...(sticky ? { top: g.heights.th } : {}) }}
                  className={cn(
                    "border-t-[0.5px] border-hair text-left",
                    // A band stays under the sticky header while its rows scroll by.
                    sticky && "sticky z-[1] bg-band-hd",
                    g.group,
                  )}
                >
                  {row.label}
                </th>
              </tr>
            );
          }
          const own = rowMatch?.(row);
          const ids = [
            ...(own === undefined ? [] : [own]),
            ...(cellMatch === undefined
              ? []
              : columns.flatMap((c) => {
                  const id = cellMatch(row, c.key);
                  return id === undefined ? [] : [id];
                })),
          ];
          return (
            <MatchRow
              key={row.id}
              ids={ids}
              id={`${gridId}-${row.id}`}
              role="row"
              aria-rowindex={rowIndex}
              aria-selected={isSelected}
              data-kind={kind}
              data-index={index}
              onClick={() => {
                select(row);
              }}
              onDoubleClick={() => {
                onOpen?.(row);
              }}
              className={cn(
                "cursor-default transition-colors duration-200",
                isSelected
                  ? "bg-sel-bg font-medium"
                  : "hover:bg-nested data-[lit]:hover:bg-match-bg",
                kind !== "item" && g.total,
                kind === "grand" && "border-b-[1.5px] border-double border-stroke",
              )}
            >
              {columns.map((c, i) => {
                const type = typeOf(c, i);
                const cell = row.cells[c.key];
                const right = rightAligned(c, type);
                const indent = type === "label" ? g.pad + (row.indent ?? 0) * g.indentStep : g.pad;
                // A line-number column hugs the label after it (leadsheet "1a", "25b").
                const line = c.line === true;
                const variance = type === "variance" ? cell?.variance : undefined;
                const vstate = variance === undefined ? null : varianceState(variance);
                return (
                  <MatchCell
                    key={c.key}
                    match={cellMatch?.(row, c.key)}
                    role="gridcell"
                    style={{
                      paddingLeft: indent,
                      paddingRight: line ? 0 : c.tick === true ? 62 : g.pad,
                      width: c.width,
                    }}
                    className={cn(
                      "relative",
                      g.td,
                      kind === "total" || kind === "grand"
                        ? "border-t-[0.5px] border-stroke"
                        : "border-t-[0.5px] border-hair",
                      right ? "text-right" : "text-left",
                      line && "text-ink-3",
                      vstate === "unexplained" && "bg-amber-tint",
                      type === "num" || type === "variance"
                        ? cn("overflow-visible whitespace-nowrap", g.numTracking)
                        : "truncate",
                    )}
                  >
                    {type === "label" ? (
                      <>
                        {row.label}
                        {row.tag !== undefined && <PropChip>{row.tag}</PropChip>}
                      </>
                    ) : type === "num" ? (
                      <MoneyCell value={cell?.value ?? null} format={c.format ?? g.format} />
                    ) : type === "variance" ? (
                      variance !== undefined && (
                        <VarianceCell variance={variance} format={c.format ?? g.format} />
                      )
                    ) : type === "chip" ? (
                      cell?.value != null &&
                      (grammar === "evidence" ? (
                        <ValueChip>{cell.value}</ValueChip>
                      ) : (
                        <PropChip>{cell.value}</PropChip>
                      ))
                    ) : (
                      (cell?.value ?? "")
                    )}
                    {cell?.tick !== undefined && <TickCell tick={cell.tick} />}
                    {vstate === "explained" && <NoteCorner />}
                  </MatchCell>
                );
              })}
              {varianceKey !== undefined && (
                <td
                  role="gridcell"
                  style={{ paddingLeft: g.pad, paddingRight: g.pad, width: ACTION_WIDTH }}
                  className={cn("border-t-[0.5px] border-hair text-right", g.td)}
                >
                  {row.cells[varianceKey]?.variance !== undefined && (
                    <VarianceAction
                      variance={row.cells[varianceKey].variance}
                      {...(onExplain === undefined
                        ? {}
                        : {
                            onExplain: () => {
                              onExplain(row, varianceKey);
                            },
                          })}
                      {...(onIssue === undefined
                        ? {}
                        : {
                            onIssue: () => {
                              onIssue(row);
                            },
                          })}
                    />
                  )}
                </td>
              )}
            </MatchRow>
          );
        })}
        {win.after > 0 && (
          <tr aria-hidden="true" style={{ height: win.after }}>
            <td colSpan={span} className="p-0" />
          </tr>
        )}
      </tbody>
    </table>
  );
  if (!win.virtual) return grid;
  return (
    <div
      ref={scroller}
      data-virtual=""
      style={{ maxHeight }}
      className={cn("relative overflow-auto", className)}
    >
      {grid}
    </div>
  );
}
