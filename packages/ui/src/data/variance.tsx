import type { JSX } from "react";
import { cn } from "../cn";
import { Button } from "../components/button";
import { Tooltip } from "../components/popover";
import { TallyPill } from "../components/status";
import { type AmountStyle, amount, parseDecimal, pct } from "../format";
import { Icon } from "../icons";
import type { VarianceState, VarianceValue } from "./types";

// The variance cell (C-01 spec 06; F-05-T43), in any grammar: Δ in the column's format, Δ% at 46
// wide, and a 13px glyph. Five states, in precedence order: posted, exception, explained, within,
// unexplained. Each says its state in words (a visually hidden word beside the glyph, the visible
// "Ties once posted"), never by colour alone. Δ and Δ% come from the server as decimal strings;
// the browser only compares |Δ| with the threshold (exactly, in bigints) and formats.

/** Each state's words. */
export const VARIANCE_WORD: Record<VarianceState, string> = {
  posted: "Ties once posted",
  exception: "Exception",
  explained: "Explained",
  within: "Within threshold",
  unexplained: "Unexplained",
};

/** |a| ≤ b, exactly, for two decimal strings. */
function absAtMost(a: string, b: string): boolean {
  const x = parseDecimal(a);
  const y = parseDecimal(b);
  const scale = Math.max(x.scale, y.scale);
  const ax = (x.units < 0n ? -x.units : x.units) * 10n ** BigInt(scale - x.scale);
  const by = y.units * 10n ** BigInt(scale - y.scale);
  return ax <= by;
}

/** The state of a variance: posted, then exception, then explained, then within, else unexplained. */
export function varianceState(v: VarianceValue): VarianceState {
  if (v.posted === true) return "posted";
  if (v.exception !== undefined) return "exception";
  if (v.explained !== undefined) return "explained";
  if (v.threshold !== undefined && absAtMost(v.value, v.threshold)) return "within";
  return "unexplained";
}

const VALUE: Record<Exclude<VarianceState, "posted">, string> = {
  within: "text-ink-3",
  unexplained: "font-medium text-amber-ink",
  explained: "text-ink",
  exception: "font-medium text-red-ink",
};

function Glyph({ state }: { state: VarianceState }): JSX.Element | null {
  switch (state) {
    case "unexplained":
      return <Icon name="triangle-alert" size={12} strokeWidth={2} className="text-amber" />;
    case "explained":
      return (
        <span className="flex size-[13px] items-center justify-center rounded-full bg-green text-on-dark">
          <Icon name="check" size={12} strokeWidth={3.4} className="size-[8px]" />
        </span>
      );
    case "exception":
      return <Icon name="flag" size={12} strokeWidth={2} className="text-red" />;
    default:
      return null;
  }
}

export interface VarianceCellProps {
  variance: VarianceValue;
  /** The column's number format. */
  format: AmountStyle;
}

/** Δ, Δ% and the state's glyph and word; "Ties once posted" replaces them all when posted. */
export function VarianceCell({ variance, format }: VarianceCellProps): JSX.Element {
  const state = varianceState(variance);
  if (state === "posted") {
    return (
      <span data-variance={state} className="inline-flex justify-end">
        <TallyPill code="ties_once_posted" />
      </span>
    );
  }
  const delta = amount(variance.value, format);
  const ratio =
    variance.ratio === null || variance.ratio === undefined || delta.tone === "zero"
      ? ""
      : pct(variance.ratio);
  const body = (
    <span
      data-variance={state}
      className="inline-flex items-center justify-end gap-[6px] whitespace-nowrap tabular-nums"
    >
      <span className={cn(delta.tone === "zero" ? "text-ink-4" : VALUE[state])}>{delta.text}</span>
      <span className="min-w-[46px] text-right text-meta font-normal text-ink-3">{ratio}</span>
      <span aria-hidden="true" className="flex size-[13px] items-center justify-center">
        <Glyph state={state} />
      </span>
      <span className="sr-only">{VARIANCE_WORD[state]}</span>
    </span>
  );
  if (state !== "explained" || variance.explained === undefined) return body;
  return (
    <Tooltip
      content={variance.explained.text}
      {...(variance.explained.by === undefined ? {} : { detail: variance.explained.by })}
    >
      {/* The hover target for the note: the amber corner marks that there is one. */}
      <span tabIndex={0} className="relative inline-flex outline-offset-2">
        {body}
      </span>
    </Tooltip>
  );
}

/** The amber corner of an explained cell: 7px, top right. */
export function NoteCorner(): JSX.Element {
  return (
    <span
      aria-hidden="true"
      data-corner=""
      className="absolute top-0 right-0 size-0 border-t-[7px] border-l-[7px] border-t-amber border-l-transparent"
    />
  );
}

export interface VarianceActionProps {
  variance: VarianceValue;
  /** "Explain…": the screen opens its explain editor. */
  onExplain?: () => void;
  /** The issue link of an exception. */
  onIssue?: () => void;
}

/** The action column beside a variance: Explain… while unexplained, the issue on an exception. */
export function VarianceAction({
  variance,
  onExplain,
  onIssue,
}: VarianceActionProps): JSX.Element | null {
  const state = varianceState(variance);
  if (state === "unexplained") {
    return (
      <Button
        variant="secondary"
        size="xs"
        opensDialog
        className="h-[22px] text-cell"
        {...(onExplain === undefined ? {} : { onClick: onExplain })}
      >
        Explain…
      </Button>
    );
  }
  if (state === "exception") {
    const issue = variance.exception?.issue;
    return (
      <button
        type="button"
        onClick={onIssue}
        className="inline-flex items-center gap-[2px] text-cell text-ink-2 hover:text-ink"
      >
        {issue === undefined ? "Issue" : `Issue ${issue}`}
        <Icon name="arrow-up-right" size={12} className="size-[11px]" />
      </button>
    );
  }
  return null;
}
