import type { JSX } from "react";
import { shown } from "./scale";
import type { ChartDatum } from "./types";

// ChartTooltip (F-08-T10; F-08 §3 D1): 220 px, the held mark's figure, its share line and an
// optional intent link ("214 · 4.8% of 4,450 due · Open in request tracker ›"). The link is an
// intent the consumer handles; the kit navigates nowhere.

export const TOOLTIP_W = 220;

export function ChartTooltip({
  datum,
  onIntent,
}: {
  datum: ChartDatum;
  onIntent?: (datum: ChartDatum) => void;
}): JSX.Element {
  const line = [shown(datum), ...(datum.share === undefined ? [] : [datum.share])].join(" · ");
  return (
    <div
      role="tooltip"
      data-chart-tooltip={datum.key}
      style={{ width: TOOLTIP_W }}
      className="absolute top-0 left-full z-10 ml-[8px] flex flex-col gap-[4px] rounded-tile bg-card px-[10px] py-[8px] text-dense shadow-e2"
    >
      <span className="font-medium text-ink">{datum.label}</span>
      <span className="text-ink-2">
        {line}
        {datum.intent !== undefined && onIntent !== undefined && (
          <>
            {" · "}
            <button
              type="button"
              className="text-ink underline-offset-2 hover:underline"
              onClick={() => {
                onIntent(datum);
              }}
            >
              {`${datum.intent} ›`}
            </button>
          </>
        )}
      </span>
    </div>
  );
}
