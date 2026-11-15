import type { JSX } from "react";
import { cn } from "../cn";

// C-38 MilestoneTimeline (A-09-T08; AUD-35 a–e; A-09 §5.6): the required communications and
// deliverables on one line of diamonds — done (olive, filled), late (brick, with "Late · n day"
// in text, never colour alone) and upcoming (outline). A list, read in order; dates arrive
// formatted by the server and Late is the server's derived state (never stored, never computed
// here).

export type MilestoneState = "upcoming" | "done" | "late";

export interface Milestone {
  key: string;
  label: string;
  /** "Nov 30". */
  due: string;
  state: MilestoneState;
  /** "Late · 1 day" or "Received Dec 2", from the server. */
  note?: string;
}

export interface MilestoneTimelineProps {
  label: string;
  milestones: readonly Milestone[];
  className?: string;
}

const DIAMOND: Record<MilestoneState, string> = {
  done: "bg-green",
  late: "bg-red",
  upcoming: "bg-card shadow-e1",
};
const WORD: Record<MilestoneState, string> = { done: "Done", late: "Late", upcoming: "Upcoming" };

export function MilestoneTimeline({
  label,
  milestones,
  className,
}: MilestoneTimelineProps): JSX.Element {
  return (
    <ol aria-label={label} className={cn("flex items-start gap-0", className)}>
      {milestones.map((m, i) => (
        <li
          key={m.key}
          className="flex min-w-0 flex-1 flex-col items-center gap-1"
          data-milestone={m.state}
        >
          <div className="flex w-full items-center">
            <span
              aria-hidden
              className={cn("h-px flex-1", i === 0 ? "bg-transparent" : "bg-stroke")}
            />
            <span aria-hidden className={cn("size-[10px] rotate-45", DIAMOND[m.state])} />
            <span
              aria-hidden
              className={cn(
                "h-px flex-1",
                i === milestones.length - 1 ? "bg-transparent" : "bg-stroke",
              )}
            />
          </div>
          <span className="truncate text-meta text-ink">{m.label}</span>
          <span className="text-meta text-ink-3 tabular-nums">{m.due}</span>
          <span className={cn("text-meta", m.state === "late" ? "text-red-ink" : "text-ink-3")}>
            {m.note ?? WORD[m.state]}
          </span>
        </li>
      ))}
    </ol>
  );
}
