import { tableFeatures, useTable } from "@tanstack/react-table";
import { type JSX, type KeyboardEvent, useId, useMemo, useState } from "react";
import { cn } from "../cn";
import { MoneyCell, PropChip, TickCell } from "./cells";
import type { ColumnType, Grammar, TableColumn, TableRow } from "./types";

// E4 DataTable engine (F-05-T27; plan 04 E4; C-01 spec 01 and 02): one headless model on
// @tanstack/react-table and a renderer per grammar. This task ships `ledger` (closes and
// reconciliations: 30px rows, 12.5px, "$" with cents) and `statement` (financial statements:
// th 30, td 26, whole dollars, uppercase group bands).
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
    th: "h-[30px] bg-band-hd text-th font-medium text-ink-3",
    td: "h-[26px]",
    pad: 10,
    indentStep: 25,
    format: "whole",
    group: "h-[24px] bg-band-hd text-group-row font-medium tracking-[0.07em] uppercase text-ink-3",
    total: "font-medium",
    numTracking: "tracking-[-0.005em]",
  },
};

function typeOf(column: TableColumn, index: number): ColumnType {
  return column.type ?? (index === 0 ? "label" : "num");
}

function rightAligned(column: TableColumn, type: ColumnType): boolean {
  return (column.align ?? (type === "num" ? "right" : "left")) === "right";
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
  className,
}: DataGridProps): JSX.Element {
  const g = GRAMMARS[grammar];
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

  function select(row: TableRow): void {
    if (selected === undefined) setOwn(row.id);
    onSelect?.(row.id, row);
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
  return (
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
        g.text,
        className,
      )}
    >
      <thead>
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
                  g.th,
                  c.entity === true && "text-body font-medium text-ink",
                  rightAligned(c, type) ? "text-right" : "text-left",
                )}
              >
                {c.header}
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody>
        {model.map((row, index) => {
          const kind = row.kind ?? "item";
          const isSelected = row.id === current;
          const rowIndex = index + 2;
          if (kind === "group") {
            return (
              <tr key={row.id} id={`${gridId}-${row.id}`} role="row" aria-rowindex={rowIndex}>
                <th
                  role="rowheader"
                  scope="rowgroup"
                  colSpan={columns.length}
                  style={pad}
                  className={cn("border-t-[0.5px] border-hair text-left", g.group)}
                >
                  {row.label}
                </th>
              </tr>
            );
          }
          return (
            <tr
              key={row.id}
              id={`${gridId}-${row.id}`}
              role="row"
              aria-rowindex={rowIndex}
              aria-selected={isSelected}
              data-kind={kind}
              onClick={() => {
                select(row);
              }}
              onDoubleClick={() => {
                onOpen?.(row);
              }}
              className={cn(
                "cursor-default transition-colors duration-200",
                isSelected ? "bg-sel-bg font-medium" : "hover:bg-nested",
                kind !== "item" && g.total,
                kind === "grand" && "border-b-[1.5px] border-double border-stroke",
              )}
            >
              {columns.map((c, i) => {
                const type = typeOf(c, i);
                const cell = row.cells[c.key];
                const right = rightAligned(c, type);
                const indent = type === "label" ? g.pad + (row.indent ?? 0) * g.indentStep : g.pad;
                return (
                  <td
                    key={c.key}
                    role="gridcell"
                    style={{
                      paddingLeft: indent,
                      paddingRight: c.tick === true ? 62 : g.pad,
                      width: c.width,
                    }}
                    className={cn(
                      "relative",
                      g.td,
                      kind === "total" || kind === "grand"
                        ? "border-t-[0.5px] border-stroke"
                        : "border-t-[0.5px] border-hair",
                      right ? "text-right" : "text-left",
                      type === "num"
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
                    ) : type === "chip" ? (
                      cell?.value != null && <PropChip>{cell.value}</PropChip>
                    ) : (
                      (cell?.value ?? "")
                    )}
                    {cell?.tick !== undefined && <TickCell tick={cell.tick} />}
                  </td>
                );
              })}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
