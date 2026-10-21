import type { JSX, ReactNode } from "react";
import { cn } from "../cn";
import { StatusDisc } from "../components/status";
import type { DiscState } from "../status";

// Timeline (C-23 Drawer "Activity"; F-05-T18): a vertical list of events in one card. Each row is a
// grid of 76 (the date, right-aligned) | 20 (a 15px status disc and a hairline down to the next
// row) | the text (a 13.5 / 500 title over a 12.5 ink-2 detail). The disc always sits beside
// words, never alone. Dates arrive formatted (format.ts); the text is a node, so agent prose goes
// through AgentText in the caller.

export interface TimelineEvent {
  id: string;
  /** The date, already formatted ("Sep 14"). */
  date: string;
  /** The disc: what the event did to the record. */
  state: DiscState;
  title: ReactNode;
  detail?: ReactNode;
}

export interface TimelineProps {
  events: readonly TimelineEvent[];
  /** The list's accessible name. */
  label: string;
  className?: string;
}

export function Timeline({ events, label, className }: TimelineProps): JSX.Element {
  return (
    <ol
      aria-label={label}
      data-shell="timeline"
      className={cn(
        "m-[10px] rounded-pane bg-card px-[14px] pt-[14px] pb-[4px] shadow-e1",
        className,
      )}
    >
      {events.map((event, i) => (
        <li
          key={event.id}
          className="relative grid grid-cols-[76px_20px_minmax(0,1fr)] gap-[10px] pb-[16px]"
        >
          <span className="pt-[2px] text-right text-meta text-ink-3">{event.date}</span>
          <span className="relative flex justify-center">
            <StatusDisc state={event.state} />
            {i < events.length - 1 && (
              <i aria-hidden="true" className="absolute top-[20px] -bottom-[16px] w-px bg-hair" />
            )}
          </span>
          <span className="flex flex-col gap-[3px]">
            <span className="text-chat leading-[1.3] font-medium">{event.title}</span>
            {event.detail !== undefined && (
              <span className="text-dense leading-[1.4] text-ink-2">{event.detail}</span>
            )}
          </span>
        </li>
      ))}
    </ol>
  );
}
