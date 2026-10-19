import { CircleX, Inbox } from "lucide-react";
import type { HTMLAttributes, JSX, ReactNode } from "react";
import { cn } from "../cn";

/** A pane: white, radius 12, a 0.5px ring and soft lift; never a CSS border (TASK-091). */
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>): JSX.Element {
  return <div className={cn("rounded-pane bg-card p-4 shadow-e2", className)} {...props} />;
}

export type Tone = "neutral" | "success" | "warning" | "danger" | "info";
const TONES: Record<Tone, string> = {
  neutral: "bg-chip text-ink-2",
  success: "bg-green-tint text-green-ink",
  warning: "bg-amber-tint text-amber-ink",
  danger: "bg-red-tint text-red-ink",
  info: "bg-amber-tint text-amber-ink",
};

export function Badge({
  tone = "neutral",
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }): JSX.Element {
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center rounded-[5px] px-1.5 text-[11.5px] leading-none font-medium tracking-[-0.005em]",
        TONES[tone],
        className,
      )}
      {...props}
    />
  );
}

/** Loading bars: 9px, nested greige, pulsing after a short delay so fast loads never flash. */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>): JSX.Element {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "min-h-[9px] animate-pulse rounded-[4.5px] bg-nested [animation-delay:200ms]",
        className,
      )}
      {...props}
    />
  );
}

/** An arc spinner: ink-2 on a faint track, 820ms a turn. */
export function Spinner({ label }: { label: string }): JSX.Element {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-[12.5px] text-ink-2">
      <svg
        aria-hidden="true"
        viewBox="0 0 16 16"
        className="size-3.5 animate-spin [animation-duration:820ms]"
      >
        <circle cx="8" cy="8" r="6.25" fill="none" stroke="rgba(43,31,23,.14)" strokeWidth="1.5" />
        <circle
          cx="8"
          cy="8"
          r="6.25"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeDasharray="11 40"
        />
      </svg>
      {label}
    </span>
  );
}

/** An error row: a brick disc, the title in brick ink, the cause in ink-2, and the way out.
 * Never a full red background. */
export function Alert({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}): JSX.Element {
  return (
    <div
      role="alert"
      className="flex items-start gap-2.5 rounded-pane bg-card px-3.5 py-3 shadow-e1"
    >
      <CircleX aria-hidden="true" className="mt-px size-4 shrink-0 text-red" />
      <div className="flex-1 text-[12.5px] leading-[1.5]">
        <p className="font-medium text-red-ink">{title}</p>
        {children !== undefined && <div className="text-ink-2">{children}</div>}
      </div>
      {action}
    </div>
  );
}

/** An empty state: a small recessed tile, a title, one line of help and at most one action. */
export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}): JSX.Element {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-8 text-center">
      <span className="flex size-[34px] items-center justify-center rounded-tile bg-nested">
        <Inbox aria-hidden="true" className="size-[17px] text-ink-3" />
      </span>
      <p className="text-[14px] font-medium">{title}</p>
      {children !== undefined && (
        <div className="max-w-[300px] text-[12.5px] leading-[1.5] text-ink-2">{children}</div>
      )}
      {action}
    </div>
  );
}
