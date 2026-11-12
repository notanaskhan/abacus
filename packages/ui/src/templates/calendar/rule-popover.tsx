// RulePopover (F-07-T11; F-07 §F2; T13a): O1 320 on `--e-note` over a chip after 250 ms of hover,
// or at once on keyboard focus. Title, then Rule (C21 text, DEC-76: data, never composed here),
// Due, Stage, Team, Blockers and "Open return →" as an intent. A postponed chip shows the struck
// original date and the relief pill (TPL-13e).
import { type JSX, useCallback, useEffect, useRef, useState } from "react";
import { shortDay } from "./dates";
import type { CalendarCopy, CalendarListCopy, DeadlineChip } from "./types";

export const HOVER_INTENT_MS = 250;

/** Hover intent: `onHover` arms a 250 ms timer, focus opens at once, leave cancels and closes. */
export function useRulePopover(): {
  open: { chip: DeadlineChip; anchor: HTMLElement } | null;
  hover: (chip: DeadlineChip, anchor: HTMLElement) => void;
  focus: (chip: DeadlineChip, anchor: HTMLElement) => void;
  leave: () => void;
} {
  const [open, setOpen] = useState<{ chip: DeadlineChip; anchor: HTMLElement } | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clear = () => {
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = null;
  };
  useEffect(() => clear, []);
  const hover = useCallback((chip: DeadlineChip, anchor: HTMLElement) => {
    clear();
    timer.current = setTimeout(() => {
      setOpen({ chip, anchor });
    }, HOVER_INTENT_MS);
  }, []);
  const focus = useCallback((chip: DeadlineChip, anchor: HTMLElement) => {
    clear();
    setOpen({ chip, anchor });
  }, []);
  const leave = useCallback(() => {
    clear();
    setOpen(null);
  }, []);
  return { open, hover, focus, leave };
}

export function RulePopover({
  chip,
  copy,
  listCopy,
  onOpenReturn,
}: {
  chip: DeadlineChip;
  copy: Pick<CalendarCopy, "postponed">;
  listCopy: Pick<CalendarListCopy, "rule" | "due" | "stage" | "team" | "blockers" | "openReturn">;
  onOpenReturn?: (chip: DeadlineChip) => void;
}): JSX.Element {
  const rows: [string, string | undefined][] = [
    [listCopy.rule, chip.rule],
    [listCopy.due, shortDay(chip.date)],
    [listCopy.stage, chip.stage],
    [listCopy.team, chip.team],
    [listCopy.blockers, chip.blockers],
  ];
  return (
    <div
      role="tooltip"
      data-rule-popover={chip.id}
      className="flex w-[320px] flex-col gap-[6px] rounded-[10px] bg-white p-[12px] shadow-note"
    >
      <p className="text-[12.5px] font-medium text-ink">{chip.title ?? chip.label}</p>
      <dl className="grid grid-cols-[72px_1fr] gap-x-[8px] gap-y-[4px] text-[12px]">
        {rows
          .filter(([, v]) => v !== undefined)
          .map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-ink-3">{k}</dt>
              <dd className="text-ink">
                {k === listCopy.due && chip.postponedTo !== undefined ? (
                  <>
                    <s>{v}</s> {copy.postponed(shortDay(chip.postponedTo))}
                  </>
                ) : (
                  v
                )}
              </dd>
            </div>
          ))}
      </dl>
      <button
        type="button"
        className="self-start text-[12px] text-ink underline-offset-2 hover:underline"
        onClick={() => onOpenReturn?.(chip)}
      >
        {listCopy.openReturn}
      </button>
    </div>
  );
}
