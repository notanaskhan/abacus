import type { JSX } from "react";
import { cn } from "../cn";
import { Amount } from "../components/amount";
import type { AmountStyle } from "../format";
import { Icon } from "../icons";
import type { Tickmark } from "./types";

// The cells every E4 grammar shares (C-01): money through format.ts, tickmarks, the micro tag.

export interface MoneyCellProps {
  /** A decimal string from the server; null renders blank. */
  value: string | null;
  format: AmountStyle;
  className?: string | undefined;
}

/**
 * A number: right-aligned tabular figures, negatives in red parentheses, zero an ink-4 dash,
 * blank empty. Never truncated (overflow stays visible; the column widens instead).
 */
export function MoneyCell({ value, format, className }: MoneyCellProps): JSX.Element {
  if (value === null) return <span className={className} />;
  return (
    <Amount
      value={value}
      style={format}
      className={cn("whitespace-nowrap tabular-nums", className)}
      data-money=""
    />
  );
}

const TICK_WORD: Record<Tickmark, string> = {
  MS: "Matched to source",
  Received: "Received",
  PY: "Agreed to prior year",
  TB: "Agreed to trial balance",
  F: "Footed",
  check: "Agreed",
};

/**
 * A tickmark pinned 10px from the cell's right edge (the column carries `tick`). MS and Received
 * are green pills with a check; `check` is a bare ink-3 check; PY, TB and F are neutral pills.
 */
export function TickCell({ tick }: { tick: Tickmark }): JSX.Element {
  const label = TICK_WORD[tick];
  if (tick === "check") {
    return (
      <span
        role="img"
        aria-label={label}
        data-tick={tick}
        className="absolute top-1/2 right-[10px] flex h-[18px] w-[31px] -translate-y-1/2 items-center pl-[5px] text-ink-3"
      >
        <Icon name="check" size={12} strokeWidth={2.2} />
      </span>
    );
  }
  const green = tick === "MS" || tick === "Received";
  return (
    <span
      role="img"
      aria-label={label}
      data-tick={tick}
      className={cn(
        "absolute top-1/2 right-[10px] inline-flex h-[18px] -translate-y-1/2 items-center gap-[3px] rounded-pill pr-[6px] pl-[5px] text-micro leading-none font-medium tracking-normal",
        green ? "bg-green text-on-dark shadow-e1" : "bg-chip text-ink-2",
      )}
    >
      {green && <Icon name="check" size={12} strokeWidth={2.4} className="size-[9px]" />}
      {tick}
    </span>
  );
}

/** The micro tag after a name (GP, LP): 18px, `chip`-ish nested fill with a hair ring, 10.5/500. */
export function PropChip({ children }: { children: string }): JSX.Element {
  return (
    <span className="ml-[6px] inline-flex h-[18px] items-center rounded-pill bg-nested px-[7px] text-micro font-medium text-ink-2 inset-ring-[0.5px] inset-ring-hair">
      {children}
    </span>
  );
}

/** An extracted value in the evidence grammar ("Level 1", "NAV"): radius 5, the selection fill,
 * a 0.5px stroke ring, ellipsis. */
export function ValueChip({ children }: { children: string }): JSX.Element {
  return (
    <span className="inline-block max-w-full truncate rounded-prop bg-sel-bg px-[6px] py-[1px] align-middle leading-[1.3] inset-ring-[0.5px] inset-ring-stroke">
      {children}
    </span>
  );
}
