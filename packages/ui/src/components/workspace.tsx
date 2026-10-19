import { Atom } from "lucide-react";
import { type HTMLAttributes, type JSX, type ReactNode, useId } from "react";
import { cn } from "../cn";
import { Badge, type Tone } from "./surfaces";

/** A status with its word, never colour alone (SPEC-016): a pill with a leading disc. */
export function StatusPill({ tone, children }: { tone: Tone; children: ReactNode }): JSX.Element {
  return (
    <Badge tone={tone} className="gap-1.5 whitespace-nowrap">
      <span
        aria-hidden="true"
        className={cn(
          "size-1.5 rounded-full",
          tone === "success" && "bg-green",
          (tone === "warning" || tone === "info") && "bg-amber",
          tone === "danger" && "bg-red",
          tone === "neutral" && "bg-ink-4",
        )}
      />
      {children}
    </Badge>
  );
}

/** Marks agent output (ADR-065, the plan's AgentMark): the atom glyph, never a boxed "AI" tag or
 * a sparkle; the citations link goes to their verified sources. Screen readers hear "AI". */
export function AiTag({ citations, href }: { citations?: number; href?: string }): JSX.Element {
  return (
    <span className="inline-flex items-center gap-1.5 text-ink-3">
      <span title="Suggested by the agent" className="inline-flex items-center">
        <Atom aria-hidden="true" className="size-[13px]" strokeWidth={1.6} />
        <span className="sr-only">AI</span>
      </span>
      {citations !== undefined && citations > 0 && href !== undefined && (
        <a
          href={href}
          className="rounded-[5px] bg-nested px-1.5 py-px text-[11px] font-medium text-ink-2 hover:bg-sel-bg hover:text-ink"
        >
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
    <span className="text-[11.5px] text-ink-3 tabular-nums">
      {done} / {total}
      {label !== undefined && ` ${label}`}
    </span>
  );
}

/** A pane with a header: title at 14.5/500 on the left, actions on the right, a hair rule. */
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
      className={cn("flex flex-col rounded-pane bg-card shadow-e2", className)}
      {...props}
    >
      <div className="flex min-h-[46px] items-center justify-between gap-2 border-b-[0.5px] border-hair px-4">
        <h2 id={id} className="text-[14.5px] font-medium tracking-[-0.012em]">
          {title}
        </h2>
        {action}
      </div>
      <div className="flex flex-col gap-3 p-4">{children}</div>
    </section>
  );
}

/** The workspace's icon rail: 44 px targets, labels for assistive technology and on hover. */
export function Rail({ label, children }: { label: string; children: ReactNode }): JSX.Element {
  return (
    <nav
      aria-label={label}
      className="flex w-full flex-row items-center gap-1 border-b-[0.5px] border-hair bg-shell px-2 py-2 sm:min-h-screen sm:w-[60px] sm:flex-col sm:border-r-[0.5px] sm:border-b-0 sm:py-3"
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
        "relative flex size-10 items-center justify-center rounded-[8px] text-ink-2 transition-colors hover:bg-nav-fill hover:text-ink [&_svg]:size-[17px]",
        active && "bg-sel-bg text-ink",
      )}
    >
      {children}
      {badge !== undefined && badge > 0 && (
        <span className="absolute top-0.5 right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red px-1 text-[10px] font-medium text-on-dark">
          {badge > 99 ? "99+" : badge}
        </span>
      )}
    </button>
  );
}
