import type { JSX } from "react";
import { cn } from "../cn";
import { Amount } from "../components/amount";
import { MATCH_CELL, useMatch } from "../tracing/match";
import type { MatchId } from "../tracing/types";

// C-38 ConsolidationWorksheet (A-09-T15; AUD-33 a, b, c, d; statement grammar): entity columns,
// the eliminations column with tag chips naming their entries, and the consolidated column.
// Whole dollars without a symbol, credits in parentheses (Amount), nil as an em dash. Every figure
// is the server's (ADR-050): the kit sums nothing, so section totals and the net income are the
// server's tallies, drawn by the caller's TallyStrip. A tag chip lights its cells (purple, the
// MatchProvider) and selects its card; `pending` draws the eliminations and consolidated columns
// in ink-2 for proposed entries (b).

export interface WorksheetCell {
  column: string;
  amount: string;
  codes?: readonly string[];
}

export interface WorksheetRow {
  caption: string;
  section: string;
  cells: readonly WorksheetCell[];
}

export interface ConsolidationWorksheetProps {
  label: string;
  /** Column keys in order, and their headers ("Holdings"). */
  columns: readonly { key: string; header: string }[];
  /** Section keys to their group-row captions ("ASSETS"). */
  sections: Readonly<Record<string, string>>;
  rows: readonly WorksheetRow[];
  /** The eliminations column's key (tag chips) and the consolidated column's (500). */
  eliminationsKey?: string;
  consolidatedKey?: string;
  /** An elimination's tag to its match id (lights the cells it touches). */
  matchOf?: (code: string) => MatchId;
  onTag?: (code: string) => void;
  /** Proposed entries: the eliminations and consolidated columns read ink-2. */
  pending?: boolean;
  className?: string;
}

function Tag({
  code,
  match,
  onTag,
}: {
  code: string;
  match: MatchId | undefined;
  onTag: ((code: string) => void) | undefined;
}): JSX.Element {
  const light = useMatch(match ?? (`elim:${code}` as MatchId), "cell");
  return (
    <button
      type="button"
      {...light.bind}
      data-tag={code}
      onClick={(event) => {
        light.pin(event.currentTarget);
        onTag?.(code);
      }}
      className={cn(
        MATCH_CELL,
        "ml-[4px] inline-flex h-[16px] items-center rounded-[4px] bg-chip px-[5px] text-[10.5px] font-medium text-ink-2",
      )}
    >
      {code}
    </button>
  );
}

function Cell({
  cell,
  strong,
  pending,
}: {
  cell: WorksheetCell | undefined;
  strong: boolean;
  pending: boolean;
}): JSX.Element {
  const nil = cell === undefined || Number(cell.amount) === 0;
  return (
    <span className={cn("tabular-nums", strong && "font-medium", pending && "text-ink-2")}>
      {nil ? <span className="text-ink-4">—</span> : <Amount value={cell.amount} style="whole" />}
    </span>
  );
}

export function ConsolidationWorksheet({
  label,
  columns,
  sections,
  rows,
  eliminationsKey = "eliminations",
  consolidatedKey = "consolidated",
  matchOf,
  onTag,
  pending = false,
  className,
}: ConsolidationWorksheetProps): JSX.Element {
  const order = Object.keys(sections);
  return (
    <table data-worksheet="" className={cn("w-full border-collapse text-[12px]", className)}>
      <caption className="sr-only">{label}</caption>
      <thead className="sticky top-0 z-[1]">
        <tr className="h-[30px] bg-nested text-[11.5px] font-medium text-ink-3">
          <th scope="col" className="w-[180px] px-[10px] text-left font-medium">
            Account
          </th>
          {columns.map((c) => (
            <th key={c.key} scope="col" className="px-[8px] text-right font-medium">
              {c.header}
            </th>
          ))}
        </tr>
      </thead>
      {order.map((section) => (
        <tbody key={section}>
          <tr className="h-[24px] bg-nested">
            <th
              colSpan={columns.length + 1}
              scope="colgroup"
              className="px-[10px] text-left text-[10px] font-medium tracking-[0.07em] text-ink-3 uppercase"
            >
              {sections[section]}
            </th>
          </tr>
          {rows
            .filter((r) => r.section === section)
            .map((r) => (
              <tr key={r.caption} data-row={r.caption} className="h-[26px] hairline-b">
                <th scope="row" className="px-[10px] text-left font-normal">
                  {r.caption}
                </th>
                {columns.map((c) => {
                  const cell = r.cells.find((x) => x.column === c.key);
                  const elim = c.key === eliminationsKey;
                  return (
                    <td
                      key={c.key}
                      data-column={c.key}
                      className="px-[8px] text-right whitespace-nowrap"
                    >
                      <Cell
                        cell={cell}
                        strong={c.key === consolidatedKey}
                        pending={pending && (elim || c.key === consolidatedKey)}
                      />
                      {elim &&
                        (cell?.codes ?? []).map((code) => (
                          <Tag key={code} code={code} match={matchOf?.(code)} onTag={onTag} />
                        ))}
                    </td>
                  );
                })}
              </tr>
            ))}
        </tbody>
      ))}
    </table>
  );
}
