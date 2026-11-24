// Specimen host frames (F-08-T19; TASK-8926; F-08 §E2; handoff TPL-24; DEC-5928): Excel and Word
// drawn in the shell's greys only, for the T22 add-in pane's specimens. Never a host brand
// colour, a Microsoft mark or Office.js: the real hosts are W-04's (ADR P-20). Exported from the
// specimens entry only (`@abacus/ui/specimens`), never from the product entry.
//
// The window: a 32 title bar (three dots, "<file> — Excel"), a 64 ribbon (a 24 tab row ending in
// "Accrued", underlined, and a 40 row of placeholder command groups), then the host's body and,
// for Excel, the 32 sheet tabs. The add-in pane sits to the right of the body (the caller passes
// it as `pane`). Excel's body is a formula bar (name box · fx · formula) over a grid of 22 rows:
// column letters, row numbers, hairline gridlines, amounts tabular right; a selected cell carries
// a 1.5 px ink ring with a 5 px handle, a linked cell C-37's dotted underline, a commented cell a
// 7 px amber corner, a changed cell the amber tint. Word's body is a page well with one white page.
import type { JSX, ReactNode } from "react";
import { cn } from "../cn";

export interface HostCell {
  text: string;
  /** Amounts and counts: tabular, right aligned. */
  numeric?: boolean;
  bold?: boolean;
  muted?: boolean;
  /** A header row cell (11 on the band fill). */
  header?: boolean;
  /** A top rule over the cell (a total row). */
  rule?: boolean;
}

export interface ExcelGridProps {
  /** Column widths in px, A first. */
  columns: readonly number[];
  rows: number;
  /** Cells by A1 address ("D14"). */
  cells: Readonly<Record<string, HostCell>>;
  selected?: string | undefined;
  linked?: readonly string[];
  commented?: readonly string[];
  changed?: readonly string[];
}

const ROW_H = 22;
const LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

function address(col: number, row: number): string {
  return `${LETTERS.charAt(col)}${String(row)}`;
}

/** The drawn Excel grid: column letters, row numbers and the cells (no zebra rows). */
export function ExcelGrid({
  columns,
  rows,
  cells,
  selected,
  linked = [],
  commented = [],
  changed = [],
}: ExcelGridProps): JSX.Element {
  const template = `34px ${columns.map((w) => `${String(w)}px`).join(" ")}`;
  return (
    <div role="grid" aria-label="Worksheet" className="min-w-0 flex-1 overflow-hidden bg-card">
      <div
        role="row"
        className="grid h-[20px] bg-band-hd text-[11px] text-ink-3"
        style={{ gridTemplateColumns: template }}
      >
        <span aria-hidden />
        {columns.map((_, c) => (
          <span
            key={LETTERS.charAt(c)}
            role="columnheader"
            className="flex items-center justify-center border-b-[0.5px] border-l-[0.5px] border-chip"
          >
            {LETTERS.charAt(c)}
          </span>
        ))}
      </div>
      {Array.from({ length: rows }, (_, i) => i + 1).map((r) => (
        <div
          key={r}
          role="row"
          className="grid text-[11.5px] text-ink"
          style={{ gridTemplateColumns: template, height: ROW_H }}
        >
          <span
            role="rowheader"
            className="flex items-center justify-center border-b-[0.5px] border-chip bg-band-hd text-[11px] text-ink-3"
          >
            {r}
          </span>
          {columns.map((_, c) => {
            const at = address(c, r);
            const cell = cells[at];
            const isSelected = selected === at;
            return (
              <span
                key={at}
                role="gridcell"
                data-cell={at}
                aria-selected={isSelected || undefined}
                className={cn(
                  "relative flex items-center overflow-hidden whitespace-nowrap border-b-[0.5px] border-l-[0.5px] border-chip px-[4px]",
                  cell?.numeric && "justify-end tabular-nums",
                  cell?.bold && "font-medium",
                  cell?.muted && "text-ink-3",
                  cell?.header && "bg-nav-fill font-medium",
                  cell?.rule && "border-t-[1px] border-t-ink-4",
                  changed.includes(at) && "bg-amber-tint",
                  isSelected && "z-10 ring-[1.5px] ring-inset ring-ink",
                )}
              >
                <span
                  className={cn(
                    linked.includes(at) &&
                      "border-b-[1px] border-dotted border-ink-4 leading-[14px]",
                  )}
                  {...(linked.includes(at) ? { "data-linked": "" } : {})}
                >
                  {cell?.text ?? ""}
                </span>
                {commented.includes(at) ? (
                  <span
                    aria-label="Comment"
                    data-comment=""
                    className="absolute right-0 top-0 h-0 w-0 border-l-[7px] border-t-[7px] border-l-transparent border-t-amber"
                  />
                ) : null}
                {isSelected ? (
                  <span
                    aria-hidden
                    className="absolute -bottom-[3px] -right-[3px] size-[5px] bg-ink"
                  />
                ) : null}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
}

export interface HostWindowProps {
  host: "excel" | "word";
  /** "AP leadsheet.xlsx". */
  file: string;
  /** The ribbon's tabs, ending in "Accrued" (the active, underlined one). */
  tabs: readonly string[];
  /** Excel only: the formula bar's name box and formula. */
  formula?: { cell: string; text: string } | undefined;
  /** Excel only: the sheet tabs, the first active. */
  sheets?: readonly string[];
  /** The add-in pane, drawn to the right of the body. */
  pane: ReactNode;
  children: ReactNode;
}

/** The drawn host window: title bar, ribbon, body (+ formula bar and sheet tabs for Excel), pane. */
export function HostWindow({
  host,
  file,
  tabs,
  formula,
  sheets = [],
  pane,
  children,
}: HostWindowProps): JSX.Element {
  const app = host === "excel" ? "Excel" : "Word";
  return (
    <div
      data-host={host}
      className="flex h-[860px] w-[1400px] flex-col overflow-hidden rounded-window bg-card shadow-e3"
    >
      <div className="relative flex h-[32px] flex-none items-center bg-nested px-[12px]">
        <span aria-hidden className="flex gap-[6px]">
          {[0, 1, 2].map((d) => (
            <span key={d} className="size-[10px] rounded-full bg-surface-deep" />
          ))}
        </span>
        <span className="absolute inset-x-0 text-center text-[12px] text-ink-2">{`${file} — ${app}`}</span>
      </div>
      <div className="flex-none border-b-[0.5px] border-hair bg-nav-fill">
        <div className="flex h-[24px] items-end gap-[14px] px-[12px] text-[11.5px] text-ink-3">
          {tabs.map((t, i) => (
            <span
              key={t}
              className={cn(i === tabs.length - 1 && "border-b-2 border-ink font-medium text-ink")}
            >
              {t}
            </span>
          ))}
        </div>
        <div aria-hidden className="flex h-[40px] items-center gap-[8px] px-[12px]">
          {[120, 160, 96, 140, 110].map((w, i) => (
            <span key={w} className="flex items-center gap-[8px]">
              {i > 0 ? <span className="h-[24px] w-[0.5px] bg-hair" /> : null}
              <span className="h-[24px] rounded-[4px] bg-chip" style={{ width: w }} />
            </span>
          ))}
        </div>
      </div>
      {formula ? (
        <div className="flex h-[28px] flex-none items-center gap-[10px] border-b-[0.5px] border-hair bg-card px-[8px] text-[12px]">
          <span className="w-[64px] border-r-[0.5px] border-hair text-ink">{formula.cell}</span>
          <span className="italic text-ink-3">fx</span>
          <span data-formula="" className="text-ink">
            {formula.text}
          </span>
        </div>
      ) : null}
      <div className="flex min-h-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex min-h-0 flex-1">{children}</div>
          {host === "excel" && sheets.length > 0 ? (
            <div className="flex h-[32px] flex-none items-center gap-[2px] bg-nav-fill px-[8px] text-[12px]">
              {sheets.map((s, i) => (
                <span
                  key={s}
                  className={cn(
                    "px-[10px] py-[4px] text-ink-2",
                    i === 0 && "rounded-[4px] bg-card font-medium text-ink",
                  )}
                >
                  {s}
                </span>
              ))}
              <span className="px-[8px] text-ink-3">+</span>
            </div>
          ) : null}
        </div>
        {pane}
      </div>
    </div>
  );
}

export interface WordPageProps {
  title: string;
  children: ReactNode;
}

/** Word's body: the grey page well with one white page. */
export function WordPage({ title, children }: WordPageProps): JSX.Element {
  return (
    <div className="flex min-w-0 flex-1 justify-center overflow-hidden bg-nested pt-[24px]">
      <article
        aria-label={title}
        className="flex h-[760px] w-[560px] flex-col gap-[8px] bg-card px-[48px] py-[40px] shadow-e1"
      >
        {children}
      </article>
    </div>
  );
}
