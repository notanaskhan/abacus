// MonthGrid (F-07-T10; T13a; F-07 §F1, §F4): the Sunday-start 7-column month under a 30 h weekday
// header (#FBFBFA, 11.5/500 ink-3). Day cells are at least 110 h; the date numeral 12.5 ink-2 top
// left, today's in a 22 px espresso circle, out-of-month numerals ink-4, a holiday's label from
// data. Each cell shows as many chips as its height fits (3 at 144 h, never more than 4) and
// "+n more" for the rest, recomputed whenever the chips change (a filter). `role="grid"`: one tab
// stop; arrows move by day, Home/End to the week's start or end, PageUp/PageDown change month;
// Enter on a day with more chips than shown opens the day popover.
import { type JSX, type KeyboardEvent, useMemo, useRef, useState } from "react";
import { cn } from "../../cn";
import { addDays, longDay, monthWeeks, WEEKDAYS, weekday } from "./dates";
import { DueChip } from "./due-chip";
import type { CalendarCopy, CalendarHoliday, DeadlineChip, ExpandedDay } from "./types";

export const HEADER_H = 30;
export const MIN_CELL_H = 110;
export const CHIP_H = 22;
const CHIP_GAP = 4;
const NUMERAL_H = 26;
const MORE_H = 18;
const PAD = 8;
export const MAX_CHIPS = 4;

/** Chips a cell of `height` shows when it holds `count` (the rest go to "+n more"). */
export function chipsThatFit(height: number, count: number): number {
  const room = (rows: number) => NUMERAL_H + PAD + rows * (CHIP_H + CHIP_GAP);
  let all = 0;
  while (all < count && all < MAX_CHIPS && room(all + 1) <= height) all += 1;
  if (all >= count) return count;
  // Leave a line for "+n more".
  let shown = 0;
  while (shown < MAX_CHIPS && room(shown + 1) + MORE_H <= height) shown += 1;
  return Math.min(shown, count);
}

export interface MonthGridProps {
  /** "2026-09". */
  month: string;
  /** Firm-local today ("2026-09-14"), passed in (P-50). */
  today: string;
  chips: readonly DeadlineChip[];
  holidays?: readonly CalendarHoliday[];
  copy: CalendarCopy;
  /** The pane's height: cells share it (at least 110 each). */
  height?: number;
  expanded?: ExpandedDay | undefined;
  onExpandDay?: (date: string) => void;
  onCloseDay?: () => void;
  onMonth?: (delta: 1 | -1) => void;
  onOpenChip?: (chip: DeadlineChip) => void;
  onHoverChip?: (chip: DeadlineChip, anchor: HTMLElement) => void;
  onFocusChip?: (chip: DeadlineChip, anchor: HTMLElement) => void;
  onLeaveChip?: () => void;
  label?: string;
}

export function MonthGrid({
  month,
  today,
  chips,
  holidays = [],
  copy,
  height = 720,
  expanded,
  onExpandDay,
  onCloseDay,
  onMonth,
  onOpenChip,
  onHoverChip,
  onFocusChip,
  onLeaveChip,
  label,
}: MonthGridProps): JSX.Element {
  const weeks = useMemo(() => monthWeeks(month), [month]);
  const byDay = useMemo(() => {
    const out = new Map<string, DeadlineChip[]>();
    for (const c of chips) out.set(c.date, [...(out.get(c.date) ?? []), c]);
    return out;
  }, [chips]);
  const holiday = useMemo(() => new Map(holidays.map((h) => [h.date, h.label])), [holidays]);
  const cellH = Math.max(MIN_CELL_H, Math.floor((height - HEADER_H) / weeks.length));
  const inMonth = (d: string) => d.startsWith(month);
  const initial = inMonth(today) ? today : `${month}-01`;
  const [focus, setFocus] = useState(initial);
  const grid = useRef<HTMLDivElement | null>(null);
  const focused = inMonth(focus) || weeks.flat().includes(focus) ? focus : initial;

  function move(next: string): void {
    setFocus(next);
    requestAnimationFrame(() => {
      grid.current?.querySelector<HTMLElement>(`[data-day="${next}"]`)?.focus();
    });
  }

  function onKey(e: KeyboardEvent<HTMLDivElement>): void {
    const d = focused;
    const keys: Record<string, () => void> = {
      ArrowLeft: () => {
        move(addDays(d, -1));
      },
      ArrowRight: () => {
        move(addDays(d, 1));
      },
      ArrowUp: () => {
        move(addDays(d, -7));
      },
      ArrowDown: () => {
        move(addDays(d, 7));
      },
      Home: () => {
        move(addDays(d, -weekday(d)));
      },
      End: () => {
        move(addDays(d, 6 - weekday(d)));
      },
      PageUp: () => {
        onMonth?.(-1);
      },
      PageDown: () => {
        onMonth?.(1);
      },
      Enter: () => {
        const n = byDay.get(d)?.length ?? 0;
        if (n > chipsThatFit(cellH, n)) onExpandDay?.(d);
      },
      Escape: () => onCloseDay?.(),
    };
    const run = keys[e.key];
    if (run === undefined) return;
    e.preventDefault();
    run();
  }

  // The day popover sits beside the grid, not in it: a grid holds rows only (axe
  // aria-required-children; DEC-4740).
  return (
    <div className="relative flex min-h-0 flex-col">
      <div
        ref={grid}
        role="grid"
        aria-label={label}
        data-month-grid={month}
        className="flex min-h-0 flex-col border-hair border-t-[0.5px] border-l-[0.5px]"
        onKeyDown={onKey}
      >
        <div role="row" className="grid grid-cols-7" style={{ height: HEADER_H }}>
          {WEEKDAYS.map((w) => (
            <div
              key={w}
              role="columnheader"
              className="flex items-center border-hair border-r-[0.5px] border-b-[0.5px] bg-band-hd px-[8px] text-[11.5px] font-medium text-ink-3"
            >
              {w}
            </div>
          ))}
        </div>
        {weeks.map((week) => (
          <div key={week[0]} role="row" className="grid grid-cols-7">
            {week.map((day) => {
              const items = byDay.get(day) ?? [];
              const shown = chipsThatFit(cellH, items.length);
              const more = items.length - shown;
              const isToday = day === today;
              return (
                <div
                  key={day}
                  role="gridcell"
                  data-day={day}
                  tabIndex={day === focused ? 0 : -1}
                  aria-label={`${longDay(day)}, ${copy.deadlines(items.length)}`}
                  aria-selected={day === focused}
                  className="flex min-w-0 flex-col gap-[4px] overflow-hidden border-hair border-r-[0.5px] border-b-[0.5px] bg-card p-[4px] outline-none focus-visible:ring-[1.5px] focus-visible:ring-espresso focus-visible:ring-inset"
                  style={{ height: cellH }}
                >
                  <span className="flex h-[22px] items-center gap-[6px]">
                    <span
                      className={cn(
                        "flex h-[22px] min-w-[22px] items-center justify-center text-[12.5px]",
                        isToday && "rounded-full bg-espresso text-on-dark",
                        // Days outside the month in ink-3: ink-4 fails 4.5:1 on the card (DEC-4740).
                        !isToday && (inMonth(day) ? "text-ink-2" : "text-ink-3"),
                      )}
                      {...(isToday ? { "data-today": "" } : {})}
                    >
                      {Number(day.slice(8))}
                    </span>
                    {holiday.has(day) ? (
                      <span className="truncate text-[11px] text-ink-3">{holiday.get(day)}</span>
                    ) : null}
                  </span>
                  {items.slice(0, shown).map((c) => (
                    <DueChip
                      key={c.id}
                      chip={c}
                      copy={copy}
                      {...(onOpenChip === undefined ? {} : { onOpen: onOpenChip })}
                      {...(onHoverChip === undefined ? {} : { onHover: onHoverChip })}
                      {...(onFocusChip === undefined ? {} : { onFocusIn: onFocusChip })}
                      {...(onLeaveChip === undefined ? {} : { onLeave: onLeaveChip })}
                    />
                  ))}
                  {more > 0 ? (
                    <button
                      type="button"
                      tabIndex={-1}
                      data-more={day}
                      className="self-start text-[11.5px] text-ink-3 hover:text-ink"
                      onClick={() => onExpandDay?.(day)}
                    >
                      {copy.more(more)}
                    </button>
                  ) : null}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      {expanded === undefined ? null : (
        <DayPopover
          day={expanded}
          chips={byDay.get(expanded.date) ?? []}
          copy={copy}
          {...(onCloseDay === undefined ? {} : { onClose: onCloseDay })}
          {...(onOpenChip === undefined ? {} : { onOpenChip })}
        />
      )}
    </div>
  );
}

/** The O1 300 px day popover: the server's header and every item that day. */
export function DayPopover({
  day,
  chips,
  copy,
  onClose,
  onOpenChip,
}: {
  day: ExpandedDay;
  chips: readonly DeadlineChip[];
  copy: CalendarCopy;
  onClose?: () => void;
  onOpenChip?: (chip: DeadlineChip) => void;
}): JSX.Element {
  return (
    <div
      role="dialog"
      aria-label={day.header}
      data-day-popover={day.date}
      className="absolute top-[40px] right-[12px] z-10 flex w-[300px] flex-col gap-[6px] rounded-[10px] bg-card p-[12px] shadow-note"
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose?.();
      }}
    >
      <p className="text-[12.5px] font-medium text-ink">{day.header}</p>
      <ul className="flex flex-col gap-[4px]">
        {chips.map((c) => (
          <li key={c.id}>
            <DueChip
              chip={c}
              copy={copy}
              tabIndex={0}
              {...(onOpenChip === undefined ? {} : { onOpen: onOpenChip })}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}
