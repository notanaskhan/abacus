import {
  type JSX,
  type KeyboardEvent,
  type PointerEvent,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { cn } from "../cn";
import { Tooltip } from "../components/popover";
import { matchIdOf } from "../tracing/match-store";
import { MatchCell, MatchRow } from "./match-cells";
import { VIRTUAL_HEIGHT, useRowWindow } from "./row-window";
import { NoteCorner } from "./variance";

// The grid grammar (C-01 spec 04; F-05-T52): an Excel-like workbook for a rendered audit program,
// an internal control workbook or any .xlsx preview. Column letters (A … Z, AA …) over 26px, a
// 34px row-number column, a hair on the right and bottom of every cell (the only grammar with
// vertical rules), td 27 at 12px. `headerRow` draws the first data row as the workbook's own
// header, espresso: the one coloured header row allowed, and never selectable. `cite` lights a
// cell or a range statically; with `source`, every cell carries the `<file>!<cell>` match id of
// its sheet-cell locator (INV-2), so a citation anywhere on the page lights it live. Comments put
// an amber corner on their cell. Column widths resize from a handle on the header (minimum 40).
// Above 200 rows it virtualises and the letter row stays sticky.

export interface GridColumn {
  key: string;
  /** px. */
  width: number;
  align?: "left" | "right";
}

export interface GridRow {
  id: string;
  cells: Readonly<Record<string, string | null | undefined>>;
}

export interface GridComment {
  by: string;
  text: string;
}

export interface GridTableProps {
  /** The accessible name ("Investments.xlsx"). */
  label: string;
  columns: readonly GridColumn[];
  rows: readonly GridRow[];
  /** The first row is the workbook's own header row. */
  headerRow?: boolean;
  /** The workbook's file name: cells carry `data-match="<file>!<cell>"`. */
  source?: string;
  /** The sheet the cells are on (the locator's `sheet`). */
  sheet?: string;
  /** A cell or range to light statically: "B4", "Investments!B4", "D6:D7". */
  cite?: string;
  /** Comments by cell ref ("G5"). */
  comments?: Readonly<Record<string, GridComment>>;
  selected?: string | null;
  onSelect?: (id: string, row: GridRow) => void;
  onOpen?: (row: GridRow) => void;
  /** Default true: drag a header's right edge to resize its column. */
  resizable?: boolean;
  /** Default: virtualise at 200 rows and above. */
  virtualize?: boolean;
  maxHeight?: number;
  className?: string;
}

/** The column letter of a zero-based index: 0 → A, 25 → Z, 26 → AA. */
export function columnLetter(index: number): string {
  let n = index + 1;
  let out = "";
  while (n > 0) {
    const r = (n - 1) % 26;
    out = String.fromCharCode(65 + r) + out;
    n = Math.floor((n - 1) / 26);
  }
  return out;
}

function columnIndex(letters: string): number {
  let n = 0;
  for (let i = 0; i < letters.length; i++) n = n * 26 + (letters.charCodeAt(i) - 64);
  return n - 1;
}

/** The cells a citation names: "B4", "Sheet!B4", or a range "D6:D7", as `[column, row]` pairs
 * (row one-based). An unreadable reference names nothing. */
export function citedCells(cite: string | undefined): readonly (readonly [number, number])[] {
  if (cite === undefined) return [];
  const ref = cite.includes("!") ? cite.slice(cite.lastIndexOf("!") + 1) : cite;
  const parse = (part: string): [number, number] | null => {
    const m = /^([A-Z]+)(\d+)$/.exec(part.trim().toUpperCase());
    return m?.[1] === undefined || m[2] === undefined
      ? null
      : [columnIndex(m[1]), Number.parseInt(m[2], 10)];
  };
  const [a, b] = ref.split(":");
  const from = a === undefined ? null : parse(a);
  const to = b === undefined ? from : parse(b);
  if (from === null || to === null) return [];
  const out: [number, number][] = [];
  for (let r = Math.min(from[1], to[1]); r <= Math.max(from[1], to[1]); r++) {
    for (let c = Math.min(from[0], to[0]); c <= Math.max(from[0], to[0]); c++) out.push([c, r]);
  }
  return out;
}

const ROW_H = 27;
const HEAD_H = 26;
const NUMBER_W = 34;
const MIN_W = 40;
const STEP = 16;

const HAIR = "border-r-[0.5px] border-b-[0.5px] border-hair";

export function GridTable({
  label,
  columns,
  rows,
  headerRow = false,
  source,
  sheet = "",
  cite,
  comments = {},
  selected,
  onSelect,
  onOpen,
  resizable = true,
  virtualize,
  maxHeight = VIRTUAL_HEIGHT,
  className,
}: GridTableProps): JSX.Element {
  const gridId = useId();
  const [widths, setWidths] = useState<Readonly<Record<string, number>>>({});
  const width = (c: GridColumn): number => widths[c.key] ?? c.width;
  const [own, setOwn] = useState<string | null>(null);
  const current = selected === undefined ? own : selected;
  const cited = useMemo(() => citedCells(cite), [cite]);
  const citedRows = useMemo(() => new Set(cited.map(([, r]) => r)), [cited]);
  const isCited = (c: number, r: number): boolean => cited.some(([x, y]) => x === c && y === r);
  const stops = rows.filter((_, i) => !(headerRow && i === 0));
  const scroller = useRef<HTMLDivElement>(null);
  const win = useRowWindow({
    count: rows.length,
    size: () => ROW_H,
    scroller,
    enabled: virtualize,
    height: maxHeight,
  });

  function select(row: GridRow): void {
    if (selected === undefined) setOwn(row.id);
    onSelect?.(row.id, row);
    if (win.virtual) win.scrollTo(rows.indexOf(row));
  }

  function onKeyDown(event: KeyboardEvent<HTMLTableElement>): void {
    const target = event.target as HTMLElement;
    if (target !== event.currentTarget) return;
    if (stops.length === 0) return;
    const at = stops.findIndex((r) => r.id === current);
    const move = (to: number): void => {
      event.preventDefault();
      const row = stops[Math.max(0, Math.min(stops.length - 1, to))];
      if (row !== undefined) select(row);
    };
    if (event.key === "ArrowDown") move(at < 0 ? 0 : at + 1);
    else if (event.key === "ArrowUp") move(at < 0 ? 0 : at - 1);
    else if (event.key === "Home") move(0);
    else if (event.key === "End") move(stops.length - 1);
    else if (event.key === "Enter") {
      const row = stops[at];
      if (row !== undefined) {
        event.preventDefault();
        onOpen?.(row);
      }
    }
  }

  const resize = (key: string, next: number): void => {
    setWidths((w) => ({ ...w, [key]: Math.max(MIN_W, Math.round(next)) }));
  };

  // The table's layout width in px (34 + the column widths): geometry, never a figure.
  let tableWidth = NUMBER_W;
  for (const c of columns) tableWidth += width(c);
  const sticky = win.virtual;
  const table = (
    <table
      role="grid"
      aria-label={label}
      aria-rowcount={rows.length + 1}
      aria-colcount={columns.length + 1}
      aria-activedescendant={current === null ? undefined : `${gridId}-${current}`}
      tabIndex={0}
      data-grammar="grid"
      onKeyDown={onKeyDown}
      style={{ width: tableWidth }}
      className="table-fixed border-collapse text-cell tracking-[-0.005em] focus-visible:outline-offset-[-2px]"
    >
      <colgroup>
        <col style={{ width: NUMBER_W }} />
        {columns.map((c) => (
          <col key={c.key} style={{ width: width(c) }} />
        ))}
      </colgroup>
      <thead>
        <tr role="row" aria-rowindex={1}>
          <th
            role="columnheader"
            aria-label="Row"
            className={cn("h-[26px] bg-band-hd", HAIR, sticky && "sticky top-0 z-[2]")}
          />
          {columns.map((c, i) => {
            const letter = columnLetter(i);
            return (
              <th
                key={c.key}
                role="columnheader"
                scope="col"
                className={cn(
                  "group relative h-[26px] bg-band-hd px-[8px] text-center text-meta font-normal text-ink-3",
                  HAIR,
                  sticky && "sticky top-0 z-[2]",
                )}
              >
                {letter}
                {resizable && (
                  <ResizeHandle
                    letter={letter}
                    width={width(c)}
                    onResize={(next) => {
                      resize(c.key, next);
                    }}
                  />
                )}
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody>
        {win.before > 0 && (
          <tr aria-hidden="true" style={{ height: win.before }}>
            <td colSpan={columns.length + 1} className="p-0" />
          </tr>
        )}
        {win.indexes.map((index) => {
          const row = rows[index];
          if (row === undefined) return null;
          const n = index + 1;
          const head = headerRow && index === 0;
          const isSelected = !head && row.id === current;
          const ids =
            source === undefined
              ? []
              : columns.map((_, c) =>
                  matchIdOf({
                    kind: "sheet_cell",
                    file: source,
                    sheet,
                    cell: `${columnLetter(c)}${String(n)}`,
                  }),
                );
          return (
            <MatchRow
              key={row.id}
              ids={ids}
              id={`${gridId}-${row.id}`}
              role="row"
              aria-rowindex={index + 2}
              {...(head ? {} : { "aria-selected": isSelected })}
              data-index={index}
              data-head={head ? "" : undefined}
              data-cited={citedRows.has(n) ? "" : undefined}
              onClick={() => {
                if (!head) select(row);
              }}
              onDoubleClick={() => {
                if (!head) onOpen?.(row);
              }}
              className={cn(
                "cursor-default transition-[background-color] duration-200",
                head
                  ? "bg-espresso font-medium text-on-dark"
                  : isSelected
                    ? "bg-sel-bg font-medium"
                    : citedRows.has(n)
                      ? "bg-match-bg"
                      : "hover:bg-nested data-[lit]:hover:bg-match-bg",
              )}
            >
              <td
                role="rowheader"
                className={cn(
                  "h-[27px] bg-band-hd text-center text-meta font-normal text-ink-3",
                  HAIR,
                )}
              >
                {n}
              </td>
              {columns.map((c, ci) => {
                const ref = `${columnLetter(ci)}${String(n)}`;
                const note = comments[ref];
                const exact = isCited(ci, n);
                return (
                  <MatchCell
                    key={c.key}
                    match={ids[ci]}
                    role="gridcell"
                    data-cell={ref}
                    {...(exact ? { "data-cited": "" } : {})}
                    className={cn(
                      "relative h-[27px] truncate px-[8px] whitespace-nowrap",
                      HAIR,
                      head && "border-on-dark/18",
                      c.align === "right" ? "text-right tabular-nums" : "text-left",
                      exact &&
                        "bg-match-bg-2 font-medium text-match-ink inset-ring-[1.5px] inset-ring-match-line transition-[background-color,box-shadow,color] duration-[360ms]",
                    )}
                  >
                    {row.cells[c.key] ?? ""}
                    {note !== undefined && (
                      <>
                        <Tooltip
                          content={<span className="font-medium">{note.by}</span>}
                          detail={note.text}
                        >
                          <span data-comment={ref} className="absolute top-0 right-0 size-[10px]">
                            <NoteCorner />
                          </span>
                        </Tooltip>
                        <span className="sr-only">{`Comment by ${note.by}: ${note.text}`}</span>
                      </>
                    )}
                  </MatchCell>
                );
              })}
            </MatchRow>
          );
        })}
        {win.after > 0 && (
          <tr aria-hidden="true" style={{ height: win.after }}>
            <td colSpan={columns.length + 1} className="p-0" />
          </tr>
        )}
      </tbody>
    </table>
  );
  return (
    <div
      ref={scroller}
      data-virtual={win.virtual ? "" : undefined}
      style={win.virtual ? { maxHeight } : undefined}
      className={cn("relative overflow-auto", className)}
    >
      {table}
    </div>
  );
}

/** The 7px handle on a header's right edge, shown while the header is hovered or focused: drag it,
 * or ← → in 16px steps, to resize the column (minimum 40). */
function ResizeHandle({
  letter,
  width,
  onResize,
}: {
  letter: string;
  width: number;
  onResize: (width: number) => void;
}): JSX.Element {
  const start = useRef<{ x: number; w: number } | null>(null);
  return (
    <span
      role="separator"
      aria-orientation="vertical"
      aria-label={`Resize column ${letter}`}
      aria-valuenow={width}
      aria-valuemin={MIN_W}
      tabIndex={0}
      data-resize={letter}
      onPointerDown={(event: PointerEvent<HTMLSpanElement>) => {
        event.currentTarget.setPointerCapture(event.pointerId);
        start.current = { x: event.clientX, w: width };
      }}
      onPointerMove={(event: PointerEvent<HTMLSpanElement>) => {
        if (start.current !== null) onResize(start.current.w + event.clientX - start.current.x);
      }}
      onPointerUp={() => {
        start.current = null;
      }}
      onKeyDown={(event) => {
        if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
          event.preventDefault();
          onResize(width + (event.key === "ArrowRight" ? STEP : -STEP));
        }
      }}
      className="absolute top-0 -right-[4px] z-[3] flex h-full w-[7px] cursor-col-resize justify-center opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
    >
      <span className="h-full w-[1.5px] bg-ink-4" />
    </span>
  );
}

export { HEAD_H as GRID_HEAD_H, ROW_H as GRID_ROW_H };
