import { CircleX } from "lucide-react";
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
        "inline-flex h-5 items-center rounded-pill px-2 text-[11.5px] leading-none font-medium tracking-[-0.005em]",
        TONES[tone],
        className,
      )}
      {...props}
    />
  );
}

// Skeleton and EmptyState moved to components/states.tsx (F-05-T19), built on Pulse and the
// kit's 200ms wait; they are re-exported so every call site is unchanged.
export { EmptyState, Skeleton } from "./states";

// The spinner moved to components/motion.tsx (F-05-T14), where it honours reduced motion.
export { Spinner } from "./motion";

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
