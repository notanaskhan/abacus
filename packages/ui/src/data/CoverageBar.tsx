import { type JSX, useState } from "react";
import { cn } from "../cn";

// CoverageBar (A-09-T08; AUD-34 e; DV-4): two stacked horizontal bars (third-party sales and total
// assets) split into full scope, specific procedures and the rest, with "View as table" as the
// equal text path. Percentages and amounts arrive formatted by the server (coverage is computed
// after eliminations by entity attribution, ADR-050); the bar only draws the widths the server's
// numbers give. Fills are the data-viz tokens; every segment also carries its label in text.
// C-36 ChartKit absorbs it in F-08.

export interface CoverageSegment {
  key: "full_scope" | "specific_procedures" | "rest";
  label: string;
  /** Share of the total, 0–100, from the server. */
  pct: number;
  /** "39,760,000". */
  amount: string;
}

export interface CoverageMeasure {
  key: string;
  label: string;
  /** "50,760,000". */
  total: string;
  segments: readonly CoverageSegment[];
}

export interface CoverageBarProps {
  label: string;
  measures: readonly CoverageMeasure[];
  className?: string;
}

const FILL: Record<CoverageSegment["key"], string> = {
  full_scope: "bg-viz-p1",
  specific_procedures: "bg-viz-p3",
  rest: "bg-nested",
};

export function CoverageBar({ label, measures, className }: CoverageBarProps): JSX.Element {
  const [table, setTable] = useState(false);
  return (
    <section aria-label={label} className={cn("flex flex-col gap-3", className)}>
      <div className="flex justify-end">
        <button
          type="button"
          aria-pressed={table}
          className="text-dense text-ink"
          onClick={() => {
            setTable((t) => !t);
          }}
        >
          {table ? "View as bars" : "View as table"}
        </button>
      </div>
      {table ? (
        <table className="w-full text-dense">
          <thead>
            <tr className="text-left text-meta text-ink-3">
              <th scope="col">Measure</th>
              <th scope="col">Segment</th>
              <th scope="col" className="text-right">
                Amount
              </th>
              <th scope="col" className="text-right">
                Share
              </th>
            </tr>
          </thead>
          <tbody>
            {measures.flatMap((m) =>
              m.segments.map((s) => (
                <tr key={`${m.key}:${s.key}`}>
                  <td>{m.label}</td>
                  <td>{s.label}</td>
                  <td className="text-right tabular-nums">{s.amount}</td>
                  <td className="text-right tabular-nums">{`${String(s.pct)}%`}</td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      ) : (
        measures.map((m) => (
          <figure key={m.key} className="flex flex-col gap-1" data-coverage={m.key}>
            <figcaption className="flex justify-between text-dense">
              <span>{m.label}</span>
              <span className="text-ink-3 tabular-nums">{m.total}</span>
            </figcaption>
            <div
              className="flex h-[14px] w-full overflow-hidden rounded-pill bg-nested"
              aria-hidden
            >
              {m.segments.map((s) => (
                <span key={s.key} className={FILL[s.key]} style={{ width: `${String(s.pct)}%` }} />
              ))}
            </div>
            <ul className="flex gap-3 text-meta text-ink-2">
              {m.segments
                .filter((s) => s.pct > 0)
                .map((s) => (
                  <li key={s.key}>{`${s.label} ${String(s.pct)}%`}</li>
                ))}
            </ul>
          </figure>
        ))
      )}
    </section>
  );
}
