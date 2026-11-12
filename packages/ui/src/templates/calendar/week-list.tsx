// T13 Week and List views (F-07-T11; F-07 §F3; T13b–d). Week: seven columns, every item a 40 h
// row (the tier's dot, "Client · Filing" 13, the stage pill and owner initials), no "+n more".
// List: T1 IndexList with Due 110 · Client flex · Filing 200 · Rule 300 · Stage 170 · Team 90 ·
// Risk 90, in the order the server sorted them, the Risk column stating the tier in words. Both
// take the same chips as the month and never sort, filter or compute a date.
import type { JSX } from "react";
import { cn } from "../../cn";
import { status } from "../../status";
import { IndexList } from "../index-list";
import { addDays, monthDay, shortDay, WEEKDAYS, weekday } from "./dates";
import { chipName } from "./due-chip";
import type { CalendarCopy, CalendarListCopy, DeadlineChip } from "./types";

export const WEEK_ROW_H = 40;

const DOT: Readonly<Record<string, string>> = {
  overdue: "bg-red",
  due_7: "bg-red",
  due_30: "bg-amber",
  later: "bg-ink-4",
  done: "bg-green",
  postponed: "bg-ink-4",
  extended: "bg-ink-4",
};

export function riskWords(chip: DeadlineChip, copy: Pick<CalendarCopy, "postponed">): string {
  if (chip.postponedTo !== undefined) return copy.postponed(monthDay(chip.postponedTo));
  return status("filing_deadline", chip.tier).label.replace("{date}", "").trim();
}

export function WeekView({
  start,
  today,
  chips,
  copy,
  onOpenChip,
  onHoverChip,
  onFocusChip,
  onLeaveChip,
}: {
  /** The week's Sunday ("2026-09-13"). */
  start: string;
  today: string;
  chips: readonly DeadlineChip[];
  copy: CalendarCopy;
  onOpenChip?: (chip: DeadlineChip) => void;
  onHoverChip?: (chip: DeadlineChip, anchor: HTMLElement) => void;
  onFocusChip?: (chip: DeadlineChip, anchor: HTMLElement) => void;
  onLeaveChip?: () => void;
}): JSX.Element {
  const sunday = addDays(start, -weekday(start));
  const days = Array.from({ length: 7 }, (_, i) => addDays(sunday, i));
  return (
    <div
      data-week={sunday}
      className="grid min-h-0 grid-cols-7 border-hair border-t-[0.5px] border-l-[0.5px]"
    >
      {days.map((d, i) => {
        const items = chips.filter((c) => c.date === d);
        return (
          <section
            key={d}
            aria-label={`${shortDay(d)}, ${copy.deadlines(items.length)}`}
            className="flex min-w-0 flex-col border-hair border-r-[0.5px] border-b-[0.5px] bg-card"
          >
            <h3
              className={cn(
                "flex h-[30px] items-center gap-[6px] bg-band-hd px-[8px] text-[11.5px] font-medium",
                d === today ? "text-ink" : "text-ink-3",
              )}
            >
              {WEEKDAYS[i]} {Number(d.slice(8))}
            </h3>
            <ul className="flex flex-col">
              {items.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    data-week-row={c.id}
                    aria-label={chipName(c, copy)}
                    className="flex w-full items-center gap-[6px] border-hair border-b-[0.5px] px-[8px] text-left hover:bg-nav-fill"
                    style={{ height: WEEK_ROW_H }}
                    onClick={() => onOpenChip?.(c)}
                    onMouseEnter={(e) => onHoverChip?.(c, e.currentTarget)}
                    onFocus={(e) => onFocusChip?.(c, e.currentTarget)}
                    onMouseLeave={onLeaveChip}
                    onBlur={onLeaveChip}
                  >
                    <span
                      aria-hidden="true"
                      className={cn(
                        "h-[6px] w-[6px] flex-none rounded-full",
                        DOT[c.tier] ?? DOT.later,
                      )}
                    />
                    <span className="min-w-0 flex-1 truncate text-[13px] text-ink">{c.label}</span>
                    {c.stage === undefined ? null : (
                      <span className="flex-none rounded-full bg-chip px-[6px] text-[11px] text-ink-2">
                        {c.stage}
                      </span>
                    )}
                    {c.initials === undefined ? null : (
                      <span className="flex-none text-[11px] text-ink-3">{c.initials}</span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

export function ListView({
  chips,
  copy,
  listCopy,
  filtered = false,
  onClearFilters,
  onOpenChip,
}: {
  chips: readonly DeadlineChip[];
  copy: CalendarCopy;
  listCopy: CalendarListCopy;
  /** The chips are a filter's result: an empty list is filtered-empty with Clear filters. */
  filtered?: boolean;
  onClearFilters?: () => void;
  onOpenChip?: (chip: DeadlineChip) => void;
}): JSX.Element {
  const state =
    chips.length > 0
      ? ({ kind: "ready" } as const)
      : filtered
        ? ({
            kind: "filtered-empty",
            title: copy.empty,
            ...(onClearFilters === undefined ? {} : { clear: onClearFilters }),
          } as const)
        : ({ kind: "empty" } as const);
  return (
    <IndexList<DeadlineChip>
      title={listCopy.title}
      noun={listCopy.noun}
      state={state}
      envelope={{ items: chips, next_cursor: null, total: chips.length, counts: {} }}
      rowKey={(c) => c.id}
      empty={{ title: copy.empty }}
      {...(onOpenChip === undefined ? {} : { onOpen: onOpenChip })}
      columns={[
        { key: "due", header: listCopy.due, width: 110, cell: (c) => shortDay(c.date) },
        { key: "client", header: listCopy.client, cell: (c) => c.client },
        { key: "filing", header: listCopy.filing, width: 200, cell: (c) => c.filing },
        { key: "rule", header: listCopy.rule, width: 300, cell: (c) => c.rule ?? "" },
        { key: "stage", header: listCopy.stage, width: 170, cell: (c) => c.stage ?? "" },
        { key: "team", header: listCopy.team, width: 90, cell: (c) => c.initials ?? "" },
        { key: "risk", header: listCopy.risk, width: 90, cell: (c) => riskWords(c, copy) },
      ]}
    />
  );
}
