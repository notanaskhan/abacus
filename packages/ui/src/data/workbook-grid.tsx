import { type JSX, type KeyboardEvent, useId, useMemo, useRef, useState } from "react";
import { cn } from "../cn";
import { citedCells, columnLetter } from "./grid";
import { VIRTUAL_HEIGHT, useRowWindow } from "./row-window";

// WorkbookGrid (T-05-T12; promoted from A-04's AUD-09 spreadsheet grid): the numbered workbook's
// cell grid for TXP-11 and every later workbook screen. Column letters over 26px, a 34px
// row-number column, a hair on the right and bottom of every cell, td 27 at 12px. One cell is
// selected: purple (the match tint) with an inset ring; cited cells carry the purple row tint;
// proposed cells an amber "Proposed" micro pill; a comment an amber corner. Above it the name box
// (the selected address) and the formula bar (the cell's formula, or "(empty) — expected …"); below
// it the sheet tabs (an amber dot on a tab with an open issue) and the "Sheet!Cell" footer.
// Keyboard (one tab stop): arrows move the selection, Enter or F2 opens the cell for editing
// (the host saves; nothing here writes), Esc cancels, and Enter in the editor commits. Above 200
// rows it virtualises and the letter row stays sticky.

export interface WorkbookCell {
  /** The value as the workbook shows it ("1,550", "(94,000)", "" when empty). */
  display: string;
  /** The formula as written back by the engine ("=F18+G18+H18"), or null for a typed value. */
  formula?: string | null;
  /** The expected formula a tie-out names for an empty cell ("='06 Schedule K'!C31 × 25% → 1,550"). */
  expected?: string;
  proposed?: boolean;
  comment?: string;
  align?: "left" | "right";
}

export interface WorkbookSheetTab {
  title: string;
  /** An open issue cites a cell on this sheet: the amber dot. */
  openIssue?: boolean;
}

export interface WorkbookGridProps {
  label: string;
  sheet: string;
  sheets: readonly WorkbookSheetTab[];
  columns: number;
  rows: number;
  /** Cells by A1 address ("H12"). A missing cell is empty. */
  cells: Readonly<Record<string, WorkbookCell>>;
  /** A cell or range lit as cited ("H8:H12"); several may be given. */
  cited?: readonly string[];
  selected: string;
  onSelect: (address: string) => void;
  onSheet?: (title: string) => void;
  /** Enter on an editor: the host saves `value` for `address` (PUT …/workbook/cells). */
  onCommit?: (address: string, value: string) => void;
  /** The footer's right side ("Cited by 1 issue · Evidence: …"). */
  footerMeta?: string;
  readOnly?: boolean;
  widths?: Readonly<Record<number, number>>;
  virtualize?: boolean;
  maxHeight?: number;
}

const ROW_H = 27;
const HEAD_H = 26;
const NUMBER_W = 34;
const DEFAULT_W = 96;
const HAIR = "border-r-[0.5px] border-b-[0.5px] border-hair";
export const EMPTY_LABEL = "(empty)";

/** "H12" → [7, 12] (zero-based column, one-based row); null for anything else. */
export function parseAddress(address: string): readonly [number, number] | null {
  const found = citedCells(address);
  return found.length === 1 ? (found[0] ?? null) : null;
}

export function addressOf(column: number, row: number): string {
  return `${columnLetter(column)}${String(row)}`;
}

/** The formula bar's text for a cell. */
export function formulaText(cell: WorkbookCell | undefined): string {
  if (cell === undefined || (cell.display === "" && !cell.formula)) {
    return cell?.expected ? `${EMPTY_LABEL} — expected ${cell.expected}` : EMPTY_LABEL;
  }
  return cell.formula ?? cell.display;
}

export function WorkbookGrid({
  label,
  sheet,
  sheets,
  columns,
  rows,
  cells,
  cited = [],
  selected,
  onSelect,
  onSheet,
  onCommit,
  footerMeta,
  readOnly = false,
  widths = {},
  virtualize,
  maxHeight,
}: WorkbookGridProps): JSX.Element {
  const id = useId();
  const scroller = useRef<HTMLDivElement | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const at = parseAddress(selected) ?? ([0, 1] as const);
  const lit = useMemo(() => {
    const out = new Set<string>();
    for (const c of cited) for (const [col, row] of citedCells(c)) out.add(addressOf(col, row));
    return out;
  }, [cited]);
  const window = useRowWindow({
    count: rows,
    size: () => ROW_H,
    scroller,
    enabled: virtualize,
    height: maxHeight ?? VIRTUAL_HEIGHT,
  });
  const current = cells[selected];

  function move(column: number, row: number): void {
    const c = Math.min(Math.max(column, 0), columns - 1);
    const r = Math.min(Math.max(row, 1), rows);
    onSelect(addressOf(c, r));
    window.scrollTo(r - 1);
  }

  function open(): void {
    if (readOnly) return;
    setEditing(selected);
    setDraft(current?.display ?? "");
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    if (editing !== null) return;
    const [column, row] = at;
    const step: Record<string, readonly [number, number]> = {
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
    };
    const delta = step[event.key];
    if (delta !== undefined) {
      event.preventDefault();
      move(column + delta[0], row + delta[1]);
    } else if (event.key === "Enter" || event.key === "F2") {
      event.preventDefault();
      open();
    }
  }

  const width = (c: number): number => widths[c] ?? DEFAULT_W;
  return (
    <div data-workbook-grid className="flex flex-col rounded-pane bg-card shadow-e1">
      <div className="flex h-[30px] items-center gap-[8px] border-b-[0.5px] border-hair px-[8px] text-[12px]">
        <output
          aria-label="Name box"
          data-name-box
          className="w-[64px] rounded-[4px] bg-nested px-[6px] font-medium"
        >
          {selected}
        </output>
        <output aria-label="Formula bar" data-formula-bar className="flex-1 truncate text-ink-2">
          {formulaText(current)}
        </output>
      </div>
      <div
        ref={scroller}
        role="grid"
        aria-label={label}
        aria-rowcount={rows}
        aria-colcount={columns}
        aria-activedescendant={`${id}-${selected}`}
        tabIndex={0}
        onKeyDown={onKeyDown}
        className="relative overflow-auto outline-none focus-visible:ring-1 focus-visible:ring-ink-3"
        style={window.virtual ? { maxHeight: maxHeight ?? VIRTUAL_HEIGHT } : undefined}
      >
        <div role="row" className="sticky top-0 z-10 flex bg-band-hd" style={{ height: HEAD_H }}>
          <span className={cn(HAIR, "shrink-0")} style={{ width: NUMBER_W }} />
          {Array.from({ length: columns }, (_, c) => (
            <span
              key={c}
              role="columnheader"
              className={cn(
                HAIR,
                "flex shrink-0 items-center justify-center text-[11px] text-ink-3",
                c === at[0] && "font-medium text-ink",
              )}
              style={{ width: width(c) }}
            >
              {columnLetter(c)}
            </span>
          ))}
        </div>
        {window.before > 0 && <div style={{ height: window.before }} />}
        {window.indexes.map((index) => {
          const row = index + 1;
          return (
            <div
              key={row}
              role="row"
              aria-rowindex={row}
              className="flex"
              style={{ height: ROW_H }}
            >
              <span
                role="rowheader"
                className={cn(
                  HAIR,
                  "flex shrink-0 items-center justify-center text-[11px] text-ink-3",
                  row === at[1] && "font-medium text-ink",
                )}
                style={{ width: NUMBER_W }}
              >
                {row}
              </span>
              {Array.from({ length: columns }, (_, c) => {
                const address = addressOf(c, row);
                const cell = cells[address];
                const isSelected = address === selected;
                const isEditing = editing === address;
                return (
                  <span
                    key={address}
                    id={`${id}-${address}`}
                    role="gridcell"
                    aria-selected={isSelected}
                    data-cell={address}
                    data-cited={lit.has(address) ? "true" : undefined}
                    data-proposed={cell?.proposed ? "true" : undefined}
                    onClick={() => {
                      onSelect(address);
                    }}
                    onDoubleClick={() => {
                      onSelect(address);
                      open();
                    }}
                    className={cn(
                      HAIR,
                      "relative flex shrink-0 items-center gap-[4px] px-[6px] text-[12px] tabular-nums",
                      cell?.align === "left" ? "justify-start" : "justify-end",
                      lit.has(address) && "bg-match-bg/40",
                      isSelected && "bg-match-bg inset-ring-1 inset-ring-match-line",
                    )}
                    style={{ width: width(c) }}
                  >
                    {isEditing ? (
                      <input
                        aria-label={`Edit ${sheet}!${address}`}
                        autoFocus
                        value={draft}
                        onChange={(e) => {
                          setDraft(e.target.value);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Escape") {
                            e.preventDefault();
                            setEditing(null);
                          } else if (e.key === "Enter") {
                            e.preventDefault();
                            setEditing(null);
                            onCommit?.(address, draft);
                          }
                        }}
                        className="w-full bg-card text-right outline-none"
                      />
                    ) : (
                      <>
                        {cell?.display}
                        {cell?.proposed ? (
                          <span className="rounded-[4px] bg-amber-tint px-[3px] text-[10.5px] text-amber-ink">
                            Proposed
                          </span>
                        ) : null}
                      </>
                    )}
                    {cell?.comment ? (
                      <span
                        aria-label={`Comment: ${cell.comment}`}
                        data-comment
                        className="absolute right-0 top-0 size-0 border-l-[6px] border-t-[6px] border-l-transparent border-t-amber"
                      />
                    ) : null}
                  </span>
                );
              })}
            </div>
          );
        })}
        {window.after > 0 && <div style={{ height: window.after }} />}
      </div>
      <nav
        aria-label="Sheets"
        className="flex h-[30px] items-center gap-[2px] border-t-[0.5px] border-hair px-[6px]"
      >
        {sheets.map((t) => (
          <button
            key={t.title}
            type="button"
            aria-current={t.title === sheet ? "page" : undefined}
            data-sheet-tab={t.title}
            onClick={() => onSheet?.(t.title)}
            className={cn(
              "flex items-center gap-[4px] rounded-[6px] px-[8px] py-[2px] text-[12px]",
              t.title === sheet ? "bg-card font-medium shadow-e1" : "text-ink-2",
            )}
          >
            {t.title}
            {t.openIssue ? (
              <span
                aria-label="Open issue"
                data-issue-dot
                className="size-[6px] rounded-full bg-amber"
              />
            ) : null}
          </button>
        ))}
      </nav>
      <footer
        data-workbook-footer
        className="flex h-[30px] items-center gap-[8px] border-t-[0.5px] border-hair px-[8px] text-[12px]"
      >
        <span className="font-medium text-ink">{`${sheet}!${selected}`}</span>
        <span className="text-ink-3">{current?.display ? current.display : "empty"}</span>
        {footerMeta ? <span className="text-ink-2">{footerMeta}</span> : null}
      </footer>
    </div>
  );
}
