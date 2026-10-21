import type { ButtonHTMLAttributes, JSX, ReactNode } from "react";
import { cn } from "../cn";
import { Icon } from "../icons";
import { PILL_WHITE, PRESS } from "./control-classes";

// Fieldset (C-13, Component Sheet R; F-05-T15): a white card of radius 10 on e1 with an optional
// header band (`band-hd`, 33 high, 13.5 / 500) and, on the right of it, one mini add button. The
// body holds free content (a form in a drawer) or, with `flush`, rows (`ValueRow`) separated by
// hairlines, which is how a settings form is drawn: no boxed inputs.

export interface FieldsetProps {
  title?: string;
  /** At the right of the header band: `FieldsetAdd`. */
  action?: ReactNode;
  /** Rows edge to edge, a hairline between them, instead of a padded body. */
  flush?: boolean;
  className?: string;
  children: ReactNode;
}

export function Fieldset({
  title,
  action,
  flush = false,
  className,
  children,
}: FieldsetProps): JSX.Element {
  return (
    <section
      className={cn("mb-[10px] overflow-hidden rounded-nested bg-card shadow-e1", className)}
    >
      {(title !== undefined || action !== undefined) && (
        <div className="flex min-h-[33px] items-center justify-between gap-[10px] border-b-[0.5px] border-hair bg-band-hd pr-[8px] pl-[12px]">
          {title !== undefined && <h3 className="min-w-0 truncate text-section">{title}</h3>}
          {action}
        </div>
      )}
      <div className={flush ? "divide-y-[0.5px] divide-hair" : "p-[12px]"}>{children}</div>
    </section>
  );
}

/** The mini add button of a fieldset header ("+ Schedule"): 25 high, white on e1, a 12px plus. */
export function FieldsetAdd({
  className,
  children,
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>): JSX.Element {
  return (
    <button
      type={type}
      className={cn(
        "relative inline-flex h-[25px] items-center gap-[4px] rounded-pill pr-[10px] pl-[8px] text-dense whitespace-nowrap",
        PRESS,
        PILL_WHITE,
        // 25px is above the 24px target, so no pseudo-element is needed.
        className,
      )}
      {...props}
    >
      <Icon name="plus" size={12} />
      {children}
    </button>
  );
}
