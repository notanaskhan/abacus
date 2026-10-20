import { ArrowDown, ArrowUp } from "lucide-react";
import { type JSX, type ReactNode, useMemo, useState } from "react";
import { cn } from "../cn";

// DataTable (TASK-101, the plan's A8.11 grid grammar): a sticky 30px band header, hair rules,
// tabular figures; optional sorting, row selection with a bulk bar, and row clicks. Plain table
// markup, so screen readers get rows and columns for free.

export interface Column<T> {
  key: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  /** A value to sort by; the column is sortable when given. */
  sortValue?: (row: T) => string | number | null;
  align?: "left" | "right";
  /** A Tailwind width class, e.g. "w-[120px]". */
  width?: string;
}

type Sort = { key: string; dir: "asc" | "desc" } | null;

export function DataTable<T>({
  label,
  rows,
  columns,
  rowKey,
  onRowClick,
  selectable = false,
  selected,
  onSelectedChange,
  canSelect,
  bulkActions,
  empty,
  initialSort = null,
  dense = false,
}: {
  label: string;
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  selectable?: boolean;
  selected?: ReadonlySet<string>;
  onSelectedChange?: (next: Set<string>) => void;
  /** Rows that can't be selected show a disabled box. */
  canSelect?: (row: T) => boolean;
  /** Shown above the table while rows are selected. */
  bulkActions?: (ids: string[]) => ReactNode;
  empty?: ReactNode;
  initialSort?: Sort;
  dense?: boolean;
}): JSX.Element {
  const [sort, setSort] = useState<Sort>(initialSort);
  const picked = selected ?? new Set<string>();
  const sorted = useMemo(() => {
    if (sort === null) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (col?.sortValue === undefined) return rows;
    const value = col.sortValue;
    return [...rows].sort((a, b) => {
      const x = value(a);
      const y = value(b);
      if (x === y) return 0;
      if (x === null) return 1;
      if (y === null) return -1;
      const order = x < y ? -1 : 1;
      return sort.dir === "asc" ? order : -order;
    });
  }, [rows, columns, sort]);
  const selectableRows = sorted.filter((r) => canSelect?.(r) ?? true);
  const allPicked =
    selectableRows.length > 0 && selectableRows.every((r) => picked.has(rowKey(r)));
  const toggle = (id: string): void => {
    const next = new Set(picked);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onSelectedChange?.(next);
  };
  const toggleAll = (): void => {
    onSelectedChange?.(allPicked ? new Set() : new Set(selectableRows.map(rowKey)));
  };
  const cellPad = dense ? "py-1.5" : "py-2";

  return (
    <div className="flex flex-col">
      {selectable && picked.size > 0 && (
        <div
          role="toolbar"
          aria-label="Selected rows"
          className="flex min-h-[40px] items-center gap-2 border-b-[0.5px] border-hair bg-sel-bg px-3 text-[12.5px]"
        >
          <span className="font-medium">{`${String(picked.size)} selected`}</span>
          <span className="flex-1" />
          {bulkActions?.([...picked])}
          <button
            type="button"
            onClick={() => onSelectedChange?.(new Set())}
            className="h-[26px] rounded-[6px] px-2.5 text-ink-2 hover:bg-nav-fill hover:text-ink"
          >
            Clear
          </button>
        </div>
      )}
      <div className="overflow-x-auto">
        <table
          aria-label={label}
          className="w-full border-collapse text-left text-[12.5px] tabular-nums"
        >
          <thead className="sticky top-0 z-[1]">
            <tr>
              {selectable && (
                <th
                  scope="col"
                  className="h-[30px] w-9 border-b-[0.5px] border-hair bg-band-hd pl-3"
                >
                  <input
                    type="checkbox"
                    aria-label="Select all"
                    checked={allPicked}
                    disabled={selectableRows.length === 0}
                    onChange={toggleAll}
                  />
                </th>
              )}
              {columns.map((c) => {
                const active = sort?.key === c.key;
                return (
                  <th
                    key={c.key}
                    scope="col"
                    aria-sort={
                      active ? (sort.dir === "asc" ? "ascending" : "descending") : undefined
                    }
                    className={cn(
                      "h-[30px] border-b-[0.5px] border-hair bg-band-hd px-3 text-[11.5px] font-normal whitespace-nowrap text-ink-2",
                      c.align === "right" && "text-right",
                      c.width,
                    )}
                  >
                    {c.sortValue !== undefined ? (
                      <button
                        type="button"
                        onClick={() => {
                          setSort(
                            active && sort.dir === "asc"
                              ? { key: c.key, dir: "desc" }
                              : active
                                ? null
                                : { key: c.key, dir: "asc" },
                          );
                        }}
                        className={cn(
                          "inline-flex items-center gap-1 hover:text-ink",
                          active && "text-ink",
                        )}
                      >
                        {c.header}
                        {active &&
                          (sort.dir === "asc" ? (
                            <ArrowUp aria-hidden="true" className="size-3" />
                          ) : (
                            <ArrowDown aria-hidden="true" className="size-3" />
                          ))}
                      </button>
                    ) : (
                      c.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => {
              const id = rowKey(row);
              const isPicked = picked.has(id);
              return (
                <tr
                  key={id}
                  aria-selected={selectable ? isPicked : undefined}
                  onClick={
                    onRowClick !== undefined
                      ? () => {
                          onRowClick(row);
                        }
                      : undefined
                  }
                  className={cn(
                    "transition-colors",
                    onRowClick !== undefined && "cursor-pointer hover:bg-shell",
                    isPicked && "bg-shell",
                  )}
                >
                  {selectable && (
                    <td className={cn("w-9 border-b-[0.5px] border-hair pl-3", cellPad)}>
                      <input
                        type="checkbox"
                        aria-label={`Select row ${id}`}
                        checked={isPicked}
                        disabled={canSelect !== undefined && !canSelect(row)}
                        onClick={(e) => {
                          e.stopPropagation();
                        }}
                        onChange={() => {
                          toggle(id);
                        }}
                      />
                    </td>
                  )}
                  {columns.map((c) => (
                    <td
                      key={c.key}
                      className={cn(
                        "border-b-[0.5px] border-hair px-3 align-middle",
                        cellPad,
                        c.align === "right" && "text-right",
                        c.width,
                      )}
                    >
                      {c.cell(row)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {sorted.length === 0 && empty}
    </div>
  );
}
