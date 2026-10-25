// SHL-08's fixture artboards (P-03-T07, T14): each scenario on the EvidenceViewer's own host, so
// `/components/screens/SHL-08?st=a–f,h` renders from its fixtures through the generated client.
// a, c–f and h are the O2 drawer held open; b is the T2 dock "Viewer" pane beside the AUD-06 trial
// balance (context only), where clicking a row re-targets the pane to that row's citation.

import { MATCH_ROW, Segmented, cn } from "@abacus/ui";
import { type JSX, useState } from "react";
import { COPY } from "./copy";
import { NORTHWIND_TB_ROWS, OPENS, type Shl08State, type Shl08TbRow } from "./scenarios";
import type { EvidenceViewerTarget } from "./EvidenceViewer";
import { ViewerDrawer } from "./ViewerDrawer";
import { ViewerPane } from "./ViewerPane";

function targetOf(state: Shl08State): EvidenceViewerTarget {
  const o = OPENS[state];
  return {
    versionId: o.versionId,
    matchId: o.matchId,
    anchor: o.anchor ?? null,
    figure: o.figure ?? null,
    hovered: o.hovered ?? null,
  };
}

function TrialBalance({
  selected,
  onSelect,
}: {
  selected: Shl08TbRow;
  onSelect: (row: Shl08TbRow) => void;
}): JSX.Element {
  return (
    <section
      aria-label={COPY.tb.title}
      className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-pane bg-card shadow-e2"
    >
      <h2 className="flex h-[46px] flex-none items-center justify-center text-pane font-medium hairline-b">
        {COPY.tb.title}
      </h2>
      <table className="w-full text-body">
        <thead>
          <tr className="h-[34px] text-th text-ink-2 hairline-b">
            <th className="px-[16px] text-left font-normal">{COPY.tb.description}</th>
            <th className="px-[16px] text-right font-normal">{COPY.tb.endOfYear}</th>
          </tr>
        </thead>
        <tbody>
          {NORTHWIND_TB_ROWS.map((row) => {
            const on = row === selected;
            return (
              <tr
                key={row.label}
                {...(on ? { "data-selected": "" } : {})}
                className={cn("h-[36px] hairline-b", on && "bg-sel-bg", MATCH_ROW)}
              >
                <td className="px-[16px]">
                  {row.anchor === null ? (
                    <span className="font-medium">{row.label}</span>
                  ) : (
                    <button
                      type="button"
                      aria-pressed={on}
                      onClick={() => {
                        onSelect(row);
                      }}
                      className="text-left"
                    >
                      {row.label}
                    </button>
                  )}
                </td>
                <td className="px-[16px] text-right tabular-nums">{row.value}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

/** SHL-08b: the trial balance and the dock, Viewer on, re-targeted by a row click. */
function DockFrame(): JSX.Element {
  const opens = OPENS.b;
  const first =
    NORTHWIND_TB_ROWS.find((r) => r.anchor?.id === opens.anchor?.id) ?? NORTHWIND_TB_ROWS[0];
  const [row, setRow] = useState<Shl08TbRow | undefined>(first);
  const target: EvidenceViewerTarget =
    row === first
      ? targetOf("b")
      : { versionId: opens.versionId, matchId: null, anchor: row?.anchor ?? null };
  return (
    <div
      data-screen="SHL-08"
      data-state="b"
      className="flex h-[860px] gap-[10px] bg-shell p-[12px]"
    >
      {row !== undefined && <TrialBalance selected={row} onSelect={setRow} />}
      <aside
        aria-label={COPY.dock.label}
        className="flex w-[330px] flex-none flex-col overflow-hidden rounded-pane bg-card shadow-e2"
      >
        <div className="flex h-[46px] flex-none items-center justify-center">
          <Segmented
            size="small"
            label={COPY.dock.label}
            options={[COPY.dock.agent, COPY.dock.viewer, COPY.dock.notes]}
            active={COPY.dock.viewer}
          />
        </div>
        <ViewerPane target={target} />
      </aside>
    </div>
  );
}

/** One SHL-08 artboard on its scenario. */
export function SHL08({ state }: { state: Shl08State }): JSX.Element {
  if (state === "b") return <DockFrame />;
  return (
    <div
      data-screen="SHL-08"
      data-state={state}
      className="flex h-[880px] justify-end bg-shell p-[10px]"
    >
      <ViewerDrawer target={targetOf(state)} open onOpenChange={() => undefined} />
    </div>
  );
}
