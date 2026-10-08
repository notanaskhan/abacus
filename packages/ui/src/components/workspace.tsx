import { type HTMLAttributes, type JSX, type ReactNode, useId } from "react";
import { cn } from "../cn";
import { Badge, type Tone } from "./surfaces";

/** A status with its word, never colour alone (SPEC-016). */
export function StatusPill({ tone, children }: { tone: Tone; children: ReactNode }): JSX.Element {
  return (
    <Badge tone={tone} className="rounded-full px-2.5 whitespace-nowrap">
      {children}
    </Badge>
  );
}

/** Marks model output; the citations link goes to their verified sources (ADR-065). */
export function AiTag({ citations, href }: { citations?: number; href?: string }): JSX.Element {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="rounded border border-ai-line px-1 text-[10px] font-bold tracking-wide text-ai">
        AI
      </span>
      {citations !== undefined && citations > 0 && href !== undefined && (
        <a href={href} className="text-xs text-accent underline-offset-2 hover:underline">
          {citations === 1 ? "1 citation" : `${String(citations)} citations`}
        </a>
      )}
    </span>
  );
}

/** Done of total, tabular. */
export function Count({
  done,
  total,
  label,
}: {
  done: number;
  total: number;
  label?: string;
}): JSX.Element {
  return (
    <span className="text-xs text-muted tabular-nums">
      {done} / {total}
      {label !== undefined && ` ${label}`}
    </span>
  );
}

export function Panel({
  title,
  action,
  className,
  children,
  ...props
}: HTMLAttributes<HTMLElement> & { title: string; action?: ReactNode }): JSX.Element {
  const id = useId();
  return (
    <section
      aria-labelledby={id}
      className={cn(
        "flex flex-col gap-3 rounded-[var(--radius-panel)] border border-line bg-surface p-4",
        className,
      )}
      {...props}
    >
      <div className="flex items-center justify-between gap-2">
        <h2 id={id} className="text-lg">
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

/** The workspace's icon rail: 44 px targets, labels for assistive technology and on hover. */
export function Rail({ label, children }: { label: string; children: ReactNode }): JSX.Element {
  return (
    <nav
      aria-label={label}
      className="flex w-full flex-row items-center gap-1 border-b border-line bg-rail px-2 py-2 sm:min-h-screen sm:w-16 sm:flex-col sm:border-r sm:border-b-0 sm:py-3"
    >
      {children}
    </nav>
  );
}

export function RailButton({
  label,
  badge,
  active = false,
  onClick,
  children,
}: {
  label: string;
  badge?: number;
  active?: boolean;
  onClick: () => void;
  children: ReactNode;
}): JSX.Element {
  return (
    <button
      type="button"
      aria-label={badge !== undefined && badge > 0 ? `${label}, ${String(badge)} unread` : label}
      aria-pressed={active}
      title={label}
      onClick={onClick}
      className={cn(
        "relative flex size-11 items-center justify-center rounded-[var(--radius-control)] text-muted hover:bg-sunken hover:text-ink",
        active && "bg-accent-soft text-accent",
      )}
    >
      {children}
      {badge !== undefined && badge > 0 && (
        <span className="absolute top-1 right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-bold text-on-accent">
          {badge > 99 ? "99+" : badge}
        </span>
      )}
    </button>
  );
}
