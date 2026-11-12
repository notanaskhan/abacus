// T13 CalendarLayout (F-07-T10; SPEC-652 AC-6; T13 handoff): under the host's toolbar, the 42 h
// subbar (left the month stepper "‹ September 2026 ›" 15/500 and Today; centred a small Segmented
// Month · Week · List; right the Office, Service and Person filter chips and Export) and one
// full-width pane. Month renders the MonthGrid; Week and List are F-07-T11's views, passed in as
// `week` and `list`. Data in, intents out: the kit never fetches, filters or computes a date.
import type { JSX, ReactNode } from "react";
import { Button } from "../../components/button";
import { Segmented } from "../../components/tabs";
import { cn } from "../../cn";
import { monthTitle } from "./dates";
import { MonthGrid } from "./month-grid";
import type {
  CalendarCopy,
  CalendarFilter,
  CalendarHoliday,
  CalendarView,
  DeadlineChip,
  ExpandedDay,
} from "./types";

export interface CalendarLayoutProps {
  view: CalendarView;
  /** "2026-09". */
  month: string;
  /** Firm-local today, passed in (P-50). */
  today: string;
  chips: readonly DeadlineChip[];
  holidays?: readonly CalendarHoliday[];
  filters?: readonly CalendarFilter[];
  copy: CalendarCopy;
  /** The day popover open on a date, with the server's header. */
  expanded?: ExpandedDay;
  /** F-07-T11's Week and List views. */
  week?: ReactNode;
  list?: ReactNode;
  height?: number;
  onView?: (view: CalendarView) => void;
  onMonth?: (delta: 1 | -1) => void;
  onToday?: () => void;
  onFilter?: (key: CalendarFilter["key"]) => void;
  onClearFilters?: () => void;
  onExport?: () => void;
  onExpandDay?: (date: string) => void;
  onCloseDay?: () => void;
  onOpenChip?: (chip: DeadlineChip) => void;
  onHoverChip?: (chip: DeadlineChip, anchor: HTMLElement) => void;
  onLeaveChip?: () => void;
  className?: string;
}

export function CalendarLayout({
  view,
  month,
  today,
  chips,
  holidays,
  filters = [],
  copy,
  expanded,
  week,
  list,
  height = 720,
  onView,
  onMonth,
  onToday,
  onFilter,
  onClearFilters,
  onExport,
  onExpandDay,
  onCloseDay,
  onOpenChip,
  onHoverChip,
  onLeaveChip,
  className,
}: CalendarLayoutProps): JSX.Element {
  const labels: Record<CalendarView, string> = {
    month: copy.month,
    week: copy.week,
    list: copy.list,
  };
  const viewOf = (label: string): CalendarView =>
    label === copy.week ? "week" : label === copy.list ? "list" : "month";
  const filtered = filters.some((f) => f.value !== undefined);
  const empty = chips.length === 0 && filtered;
  return (
    <section data-calendar={view} className={cn("flex min-h-0 flex-1 flex-col", className)}>
      <div className="relative flex h-[42px] flex-none items-center gap-[6px] px-[12px]">
        <Button
          variant="ghost"
          size="sm"
          icon="chevron-left"
          aria-label={copy.previous}
          onClick={() => onMonth?.(-1)}
        />
        <h2 className="text-[15px] font-medium text-ink">{monthTitle(month)}</h2>
        <Button
          variant="ghost"
          size="sm"
          icon="chevron-right"
          aria-label={copy.next}
          onClick={() => onMonth?.(1)}
        />
        <Button variant="secondary" size="sm" onClick={onToday}>
          {copy.today}
        </Button>
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
          <Segmented
            size="small"
            label={copy.views}
            options={[copy.month, copy.week, copy.list]}
            active={labels[view]}
            {...(onView === undefined ? {} : { onChange: (l: string) => onView(viewOf(l)) })}
          />
        </div>
        <span className="flex-1" />
        {filters.map((f) => (
          <Button
            key={f.key}
            variant={f.value === undefined ? "ghost" : "secondary"}
            size="sm"
            iconAfter="chevron-down"
            data-filter={f.key}
            onClick={() => onFilter?.(f.key)}
          >
            {f.value === undefined ? f.label : `${f.label}: ${f.value}`}
          </Button>
        ))}
        <Button variant="ghost" size="sm" iconAfter="chevron-down" onClick={onExport}>
          {copy.export}
        </Button>
      </div>
      <div className="relative min-h-0 flex-1 px-[12px] pb-[12px]">
        {empty ? (
          <div className="flex flex-col items-center gap-[8px] pt-[80px]" data-calendar-empty="">
            <p className="text-[13px] text-ink-2">{copy.empty}</p>
            <Button variant="secondary" size="sm" onClick={onClearFilters}>
              {copy.clearFilters}
            </Button>
          </div>
        ) : view === "month" ? (
          <MonthGrid
            month={month}
            today={today}
            chips={chips}
            copy={copy}
            height={height}
            label={monthTitle(month)}
            {...(holidays === undefined ? {} : { holidays })}
            {...(expanded === undefined ? {} : { expanded })}
            {...(onExpandDay === undefined ? {} : { onExpandDay })}
            {...(onCloseDay === undefined ? {} : { onCloseDay })}
            {...(onMonth === undefined ? {} : { onMonth })}
            {...(onOpenChip === undefined ? {} : { onOpenChip })}
            {...(onHoverChip === undefined ? {} : { onHoverChip })}
            {...(onLeaveChip === undefined ? {} : { onLeaveChip })}
          />
        ) : view === "week" ? (
          week
        ) : (
          list
        )}
      </div>
    </section>
  );
}
