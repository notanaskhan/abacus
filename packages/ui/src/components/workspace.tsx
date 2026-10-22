import { Atom } from "lucide-react";
import { type HTMLAttributes, type JSX, type ReactNode, useId } from "react";
import { cn } from "../cn";

// StatusPill moved to components/status.tsx with the rest of the Status kit (F-05-T12). The
// Atelier icon rail (Rail, RailButton) was retired with its tokens (F-05-T34).

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
          className="rounded-pill bg-nested px-1.5 py-px text-[11px] font-medium text-ink-2 hover:bg-sel-bg hover:text-ink"
        >
          {citations === 1 ? "1 citation" : `${String(citations)} citations`}
        </a>
      )}
    </span>
  );
}

/** Done of total as a plain line, tabular ("3 / 5 received"). Was `Count`; the C-06 Count is the
 * number pill (components/pill.tsx), and the pill for done of total is `DoneCount`. */
export function Fraction({
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
