import type { TestGridOut } from "@abacus/api-client";
import { Amount, Pill, Tick, cn } from "@abacus/ui";
import type { JSX } from "react";
import { FIELDWORK_COPY } from "./copy";
import { BlockCard } from "./je";

// The attribute-test grid (A-08-T26; AUD-12 b, c, h) on A-05's grid grammar (EBP-04 c): items
// down, attributes across, each cell the figure as recorded and code's recalculation, the result
// at the end. `details` is a test of details; `controls` adds the deviation log under it. The
// browser recalculates nothing (ADR-050).

const C = FIELDWORK_COPY;
type GridRow = TestGridOut["rows"][number];

export interface TestGridProps {
  variant: "details" | "controls";
  title: string;
  grid: TestGridOut;
  /** Attribute keys to their column headers (the handoff's words). */
  headers: Readonly<Record<string, string>>;
  /** A flagged row's note, by item ("No deferral, no opt-out → EBP-03"). */
  flags?: Readonly<Record<string, string>>;
  onFlag?: (itemId: string) => void;
}

function cellOf(
  row: GridRow,
  key: string,
): TestGridOut["rows"][number]["cells"][number] | undefined {
  return row.cells.find((c) => c.attribute_key === key);
}

const MONEY = /^-?\d+\.\d{2}$/u;

export function TestGrid({
  variant,
  title,
  grid,
  headers,
  flags = {},
  onFlag,
}: TestGridProps): JSX.Element {
  const cols = `40px 150px repeat(${String(grid.attributes.length)}, minmax(0, 1fr)) 120px`;
  return (
    <BlockCard title={title}>
      <div role="table" aria-label={title} data-fieldwork="test-grid" data-variant={variant}>
        <div
          role="row"
          style={{ gridTemplateColumns: cols }}
          className="grid h-[28px] items-center bg-nested text-[11.5px] text-ink-2"
        >
          <span role="columnheader" className="px-[8px]">
            #
          </span>
          <span role="columnheader" className="px-[8px]" />
          {grid.attributes.map((a) => (
            <span key={a} role="columnheader" className="px-[8px] text-right">
              {headers[a] ?? a}
            </span>
          ))}
          <span role="columnheader" className="px-[8px]" />
        </div>
        {grid.rows.map((r) => {
          const flag = flags[r.item_id];
          return (
            <div
              key={r.item_id}
              role="row"
              data-test-row={r.position}
              data-state={r.state}
              style={{ gridTemplateColumns: cols }}
              className={cn(
                "grid min-h-[29px] items-center text-cell hairline-b",
                flag !== undefined && "bg-red-tint",
              )}
            >
              <span role="cell" className="px-[8px] text-ink-3 tabular-nums">
                {r.position}
              </span>
              <span role="cell" className="truncate px-[8px]">
                {r.record_key}
              </span>
              {grid.attributes.map((a) => {
                const cell = cellOf(r, a);
                const v = cell?.value ?? cell?.expected ?? null;
                return (
                  <span key={a} role="cell" data-cell={a} className="px-[8px] text-right">
                    {v === null ? "—" : MONEY.test(v) ? <Amount value={v} /> : v}
                  </span>
                );
              })}
              <span role="cell" className="px-[8px]">
                {flag !== undefined ? (
                  <button
                    type="button"
                    onClick={() => onFlag?.(r.item_id)}
                    className="text-left text-[11.5px] text-red-ink"
                  >
                    {flag}
                  </button>
                ) : r.state === "pass" ? (
                  <Tick code="check" />
                ) : r.state === "exception" ? (
                  <Pill variant="red-tint">{C.grid.exception}</Pill>
                ) : (
                  <Pill variant="muted">{C.selected.result.not_started}</Pill>
                )}
              </span>
            </div>
          );
        })}
      </div>
    </BlockCard>
  );
}

export interface Deviation {
  id: string;
  item: string;
  description: string;
}

/** The test of controls' deviation log; empty, it reads the code-computed UDL against tolerable. */
export function DeviationLog({
  deviations,
  udl,
  tolerable,
}: {
  deviations: readonly Deviation[];
  /** "8.8%" and "10%": formatted by the server's figures (pct), never computed here. */
  udl: string;
  tolerable: string;
}): JSX.Element {
  return (
    <BlockCard title={C.grid.deviations}>
      {deviations.length === 0 ? (
        <p data-fieldwork="deviations-empty" className="px-[14px] py-[10px] text-cell text-ink-2">
          {C.grid.none(udl, tolerable)}
        </p>
      ) : (
        <ul data-fieldwork="deviations">
          {deviations.map((d) => (
            <li
              key={d.id}
              className="flex h-[33px] items-center gap-[12px] px-[14px] text-cell hairline-b"
            >
              <span className="w-[120px] shrink-0">{d.item}</span>
              <span className="text-ink-2">{d.description}</span>
            </li>
          ))}
        </ul>
      )}
    </BlockCard>
  );
}
