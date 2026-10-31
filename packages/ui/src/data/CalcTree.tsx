import { type JSX, type KeyboardEvent, useRef } from "react";
import { cn } from "../cn";
import { MATCH_ROW, useMatch } from "../tracing/match";
import type { MatchId } from "../tracing/types";

// The calc tree (F-06-T19; T6e; F-06 Story 5.6, INV-2): how a figure is built, step by step,
// beside the source-workbook grid. role="tree" with aria-level; one rail per level; the lit step
// takes the full-bleed match fill (#ECD9F0). Hovering or focusing a step with a match lights its
// Sheet!Cell in the grid through the shared MatchScope within the 360 ms fade; Enter pins the
// match, Escape (the scope's) clears it and returns focus. Match ids come only from typed xlsx
// locators (`matchIdOf({kind: "sheet_cell", …})`), never from text. The tree shows the server's
// steps and computes nothing (ADR-050).

export interface CalcTreeStep {
  ref: string;
  /** 0 for the result; each level below indents one rail. */
  depth: number;
  /** "", "+", "−", "×". */
  op: string;
  label: string;
  /** Formatted by the server ("938,561", "(148,500)", "—", "49.5%"). */
  value: string;
  /** "Capital!H3" or "Schedule K · line 5". */
  src: string;
  /** The step's typed sheet-cell match id, when its source is a workbook cell. */
  match?: string;
}

export interface CalcTreeProps {
  /** The tree's accessible name ("Ending Capital · Calder Family Trust"). */
  label: string;
  steps: readonly CalcTreeStep[];
  className?: string;
}

const RAIL = 25;

function Step({
  step,
  index,
  onKey,
}: {
  step: CalcTreeStep;
  index: number;
  onKey: (event: KeyboardEvent<HTMLLIElement>, index: number) => void;
}): JSX.Element {
  // A step with no workbook cell lights nothing (its src is a form line).
  const id = (step.match ?? `calc:${step.ref}`) as MatchId;
  const { lit, bind, pin } = useMatch(id, "row");
  const events = step.match === undefined ? {} : bind;
  const negative = step.value.startsWith("(");
  return (
    <li
      role="treeitem"
      aria-level={step.depth + 1}
      aria-selected={lit}
      tabIndex={index === 0 ? 0 : -1}
      data-calc-step={step.ref}
      {...events}
      onKeyDown={(event) => {
        if (event.key === "Enter" && step.match !== undefined) {
          event.preventDefault();
          pin(event.currentTarget);
          return;
        }
        onKey(event, index);
      }}
      className={cn(
        MATCH_ROW,
        "relative flex h-[44px] items-center gap-[8px] pr-[22px] text-body outline-offset-[-2px]",
      )}
      style={{ paddingLeft: 50 + step.depth * RAIL - (step.op === "" ? 0 : 20) }}
    >
      {Array.from({ length: step.depth }, (_, level) => (
        <span
          key={level}
          aria-hidden="true"
          data-rail=""
          className="absolute top-0 bottom-0 w-[0.5px] bg-stroke"
          style={{ left: 31 + level * RAIL }}
        />
      ))}
      {step.op !== "" && (
        <span aria-hidden="true" className="w-[12px] flex-none text-center text-meta text-ink-3">
          {step.op}
        </span>
      )}
      <span className="min-w-0 flex-1 truncate">{step.label}</span>
      <span
        className={cn(
          "flex-none text-meta text-ink-3",
          lit && step.match !== undefined && "text-match-ink",
        )}
      >
        {step.src}
      </span>
      <span
        className={cn(
          "w-[96px] flex-none text-right tabular-nums",
          negative ? "text-red" : step.value === "—" ? "text-ink-4" : "text-ink",
        )}
      >
        {step.value}
      </span>
    </li>
  );
}

export function CalcTree({ label, steps, className }: CalcTreeProps): JSX.Element {
  const list = useRef<HTMLUListElement>(null);
  const move = (event: KeyboardEvent<HTMLLIElement>, index: number): void => {
    const next =
      event.key === "ArrowDown"
        ? index + 1
        : event.key === "ArrowUp"
          ? index - 1
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? steps.length - 1
              : null;
    if (next === null || next < 0 || next >= steps.length) return;
    event.preventDefault();
    const items = list.current?.querySelectorAll<HTMLLIElement>("[role=treeitem]");
    const target = items?.[next];
    if (target === undefined) return;
    event.currentTarget.tabIndex = -1;
    target.tabIndex = 0;
    target.focus();
  };
  return (
    <ul
      ref={list}
      role="tree"
      aria-label={label}
      data-calc-tree=""
      className={cn("flex flex-col py-[8px]", className)}
    >
      {steps.map((step, i) => (
        <Step key={step.ref} step={step} index={i} onKey={move} />
      ))}
    </ul>
  );
}
