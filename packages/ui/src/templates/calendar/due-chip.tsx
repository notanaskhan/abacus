// DueChip (F-07-T10; F-07 §F1): 22 h, radius 999, 12 px "Client · Filing" in the server's tier:
// overdue solid brick, due within 7 days red-tint, within 30 amber-tint, later neutral, done
// green-tint with a check (12, the icon registry's smallest; the spec says 10); postponed strikes the original date and adds a muted "Postponed
// → Nov 2" pill. The accessible name states client, filing, due date and risk in words, so the
// tier is never colour alone (§11 Q1).
import type { FocusEvent, JSX, MouseEvent } from "react";
import { cn } from "../../cn";
import { Icon } from "../../icons";
import { status } from "../../status";
import { monthDay, shortDay } from "./dates";
import type { CalendarCopy, DeadlineChip } from "./types";

const TONE: Readonly<Record<string, string>> = {
  overdue: "bg-red text-on-dark",
  due_7: "bg-red-tint text-red-ink",
  due_30: "bg-amber-tint text-amber-ink",
  later: "bg-chip text-ink-2",
  done: "bg-green-tint text-green-ink",
  postponed: "bg-chip text-ink-3",
  extended: "bg-chip text-ink-2",
};

/** What assistive technology hears: "Ridgeline Property Partners, LP, Form 1065, due Tue Sep 15,
 * 2026, Due this week". */
export function chipName(chip: DeadlineChip, copy: Pick<CalendarCopy, "postponed">): string {
  const word = status("filing_deadline", chip.tier).label.replace("{date}", "");
  const risk =
    chip.postponedTo === undefined ? word.trim() : copy.postponed(monthDay(chip.postponedTo));
  return `${chip.client}, ${chip.filing}, due ${shortDay(chip.date)}, ${risk}${chip.note === undefined ? "" : `, ${chip.note}`}`;
}

export interface DueChipProps {
  chip: DeadlineChip;
  copy: Pick<CalendarCopy, "postponed">;
  onOpen?: (chip: DeadlineChip) => void;
  /** Hover for the RulePopover's 250 ms intent (F-07-T11). */
  onHover?: (chip: DeadlineChip, anchor: HTMLElement) => void;
  /** Keyboard focus opens the RulePopover at once (F-07-T11); falls back to `onHover`. */
  onFocusIn?: (chip: DeadlineChip, anchor: HTMLElement) => void;
  onLeave?: () => void;
  tabIndex?: number;
}

export function DueChip({
  chip,
  copy,
  onOpen,
  onHover,
  onFocusIn,
  onLeave,
  tabIndex = -1,
}: DueChipProps): JSX.Element {
  const postponed = chip.postponedTo !== undefined;
  const enter = (e: MouseEvent<HTMLButtonElement>) => {
    onHover?.(chip, e.currentTarget);
  };
  const focusIn = (e: FocusEvent<HTMLButtonElement>) => {
    (onFocusIn ?? onHover)?.(chip, e.currentTarget);
  };
  return (
    <span className="flex min-w-0 items-center gap-[4px]">
      <button
        type="button"
        data-chip={chip.id}
        data-tier={chip.tier}
        tabIndex={tabIndex}
        aria-label={chipName(chip, copy)}
        className={cn(
          "inline-flex h-[22px] min-w-0 items-center gap-[4px] truncate rounded-full px-[8px] text-[12px] leading-none",
          TONE[chip.tier] ?? TONE.later,
          postponed && "line-through",
        )}
        onClick={() => onOpen?.(chip)}
        onMouseEnter={enter}
        onFocus={focusIn}
        onMouseLeave={onLeave}
        onBlur={onLeave}
      >
        {chip.tier === "done" ? <Icon name="check" size={12} /> : null}
        <span className="truncate">{chip.label}</span>
        {chip.note === undefined ? null : <span className="opacity-80">{chip.note}</span>}
      </button>
      {postponed ? (
        <span
          aria-hidden="true"
          className="inline-flex h-[18px] items-center rounded-full bg-chip px-[6px] text-[11px] text-ink-3"
        >
          {copy.postponed(monthDay(chip.postponedTo ?? chip.date))}
        </span>
      ) : null}
    </span>
  );
}
