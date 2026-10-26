// A decision dock in the SHL-11 decision-card grammar (P-07-T46; CLI-07 spec.md DOCK), local to
// the engagements domain until SHL-11's own card lands: the "?" chip and the question, the
// not-ready banner or the locked decision pill, the options as 17px olive radios with a title and a
// detail line, the screen's own fields (conditions, rationale), and a pinned footer with one
// full-width action and the reserved-to note. It draws what it is given; who may choose and what
// the action does are the screen's (a person's decision, never an agent's: ADR-005).

import { Icon, Pill, type PillVariant, Radio, cn } from "@abacus/ui";
import type { JSX, ReactNode } from "react";

export interface DecisionDockOption {
  value: string;
  label: string;
  detail: string;
}

export interface DecisionDockProps {
  /** "Accept the Estate of Walter Thornbury engagement?" */
  question: string;
  options: readonly DecisionDockOption[];
  /** The option picked (or recorded, once locked). */
  chosen: string | null;
  onChoose?: (value: string) => void;
  /** The options cannot be picked: the viewer may not decide, or the record is not ready. */
  disabled?: boolean;
  /** The amber line under the question: "Not ready for decision — 1 manual check open". */
  banner?: string;
  /** The recorded decision: the options read only, with its pill and a lock. */
  decided?: { pill: string; variant: PillVariant; line: string };
  /** The screen's fields under the options (conditions, rationale). */
  children?: ReactNode;
}

/** The dock's body: question, state, options and the screen's fields. */
export function DecisionDock({
  question,
  options,
  chosen,
  onChoose,
  disabled = false,
  banner,
  decided,
  children,
}: DecisionDockProps): JSX.Element {
  const locked = decided !== undefined;
  return (
    <div data-decision-dock="" className="flex flex-col">
      <div className="flex flex-col gap-[8px] px-[12px] pt-[12px] pb-[10px] hairline-b">
        <div className="flex items-start gap-[8px]">
          <span
            aria-hidden="true"
            className="mt-[1px] flex size-[19px] flex-none items-center justify-center rounded-pill bg-nested text-meta text-ink-3"
          >
            ?
          </span>
          <h3 className="text-section leading-[1.3] font-medium">{question}</h3>
        </div>
        {banner !== undefined && (
          <p
            data-dock-banner=""
            className="rounded-nested bg-amber-tint px-[12px] py-[8px] text-body text-amber-ink"
          >
            {banner}
          </p>
        )}
        {decided !== undefined && (
          <div data-dock-decided="" className="flex flex-col gap-[4px]">
            <span className="flex items-center gap-[6px]">
              <Pill variant={decided.variant}>{decided.pill}</Pill>
              <Icon name="lock" size={12} className="text-ink-3" label="Locked" />
            </span>
            <span className="text-meta text-ink-3">{decided.line}</span>
          </div>
        )}
      </div>
      {locked ? (
        <ul aria-label={question} className="flex flex-col">
          {options.map((o) => {
            const on = o.value === chosen;
            return (
              <li
                key={o.value}
                data-option={o.value}
                {...(on ? { "data-chosen": "" } : {})}
                className={cn("flex gap-[10px] px-[12px] py-[10px] hairline-b", on && "bg-shell")}
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    "mt-[1px] flex size-[17px] flex-none items-center justify-center rounded-pill",
                    on ? "bg-green text-on-dark" : "inset-ring-[1.3px] inset-ring-rule",
                  )}
                >
                  {on && <Icon name="check" size={12} />}
                </span>
                <span className="flex min-w-0 flex-col gap-[2px]">
                  <span className={cn("text-section", on ? "text-ink" : "text-ink-3")}>
                    {o.label}
                    {on && <span className="sr-only"> (chosen)</span>}
                  </span>
                  <span className="text-body leading-[1.4] text-ink-3">{o.detail}</span>
                </span>
              </li>
            );
          })}
        </ul>
      ) : (
        <div role="radiogroup" aria-label={question} className="flex flex-col">
          {options.map((o) => {
            const on = o.value === chosen;
            return (
              <label
                key={o.value}
                data-option={o.value}
                {...(on ? { "data-chosen": "" } : {})}
                className={cn(
                  "flex gap-[10px] px-[12px] py-[10px] hairline-b",
                  on && "bg-shell",
                  !disabled && "cursor-pointer hover:bg-nested",
                )}
              >
                <Radio
                  checked={on}
                  label={o.label}
                  disabled={disabled}
                  className="mt-[1px]"
                  onSelect={() => onChoose?.(o.value)}
                />
                <span className="flex min-w-0 flex-col gap-[2px]">
                  <span className={cn("text-section", disabled ? "text-ink-3" : "text-ink")}>
                    {o.label}
                  </span>
                  <span className="text-body leading-[1.4] text-ink-2">{o.detail}</span>
                </span>
              </label>
            );
          })}
        </div>
      )}
      {children}
    </div>
  );
}

/** The dock's pinned footer: one full-width action, then the 11.5 ink-3 note. */
export function DecisionDockFooter({
  action,
  note,
}: {
  action: ReactNode;
  note: string;
}): JSX.Element {
  return (
    <div data-dock-footer="" className="flex flex-col gap-[8px]">
      {action}
      <p className="text-meta leading-[1.4] text-ink-3">{note}</p>
    </div>
  );
}
