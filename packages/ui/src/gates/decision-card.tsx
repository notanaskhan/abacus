import type { JSX, ReactNode } from "react";
import { HumanAction } from "../attribution/human-action";
import type { Actor } from "../attribution/actor";
import { Button } from "../components/button";
import { RadioGroup } from "../components/toggles";
import { cn } from "../cn";

// DecisionCard (E7; P-04-T40; SHL-11, HOME-02): a decision reserved to a named role. The options
// are a radio group; the agent's recommendation is a tag on its option, never a choice made. The
// sheet variant fills an O3 sheet; the inline variant sits in a queue's detail pane. "Decide" is
// a HumanAction: no control lets the agent decide (INV-1).

export interface DecisionOption {
  key: string;
  label: string;
  detail?: string;
  recommended?: boolean;
}

export interface DecisionCardProps {
  title: string;
  /** "Reserved to the engagement partner. The agent cannot decide." */
  reservedNote: string;
  options: readonly DecisionOption[];
  value?: string;
  onChange?: (key: string) => void;
  actor: Actor;
  /** The agent's reasons, rendered by the caller through AgentText. */
  why?: ReactNode;
  variant?: "sheet" | "inline";
  decided?: { option: string; by: string; at: string } | null;
  busy?: boolean;
  onDecide?: () => void;
  onRequestMore?: () => void;
  requestMoreLabel?: string;
  recommendationLabel?: string;
  /** The dock variant (P-04-T49; SHL-11 frame 5): instead of Decide, one primary control that
   * opens the decision sheet, where the reserved person decides. Options are read-only here. */
  openDecision?: { label: string; onOpen: () => void };
  className?: string;
}

export function DecisionCard({
  title,
  reservedNote,
  options,
  value,
  onChange,
  actor,
  why,
  variant = "inline",
  decided = null,
  busy = false,
  onDecide,
  onRequestMore,
  requestMoreLabel = "Request more analysis…",
  recommendationLabel = "Agent recommendation",
  openDecision,
  className,
}: DecisionCardProps): JSX.Element {
  const recommended = options.find((o) => o.recommended === true);
  return (
    <section
      aria-label={title}
      data-gate="decision"
      data-variant={variant}
      className={cn(
        "flex flex-col gap-[10px]",
        variant === "inline" && "rounded-nested bg-card p-[12px] shadow-e1",
        className,
      )}
    >
      <h3 className="text-section">{title}</h3>
      {why !== undefined && <div className="text-para text-ink-2">{why}</div>}
      {decided !== null ? (
        <p data-gate="decided" className="text-body">
          {decided.option}{" "}
          <span className="text-meta text-ink-3">
            · {decided.by} · {decided.at}
          </span>
        </p>
      ) : (
        <>
          <RadioGroup
            label={title}
            options={options.map((o) => ({
              value: o.key,
              label: o.label,
              ...(openDecision === undefined ? {} : { disabled: true }),
            }))}
            {...(value === undefined ? {} : { value })}
            {...(onChange === undefined || openDecision !== undefined ? {} : { onChange })}
          />
          {recommended !== undefined && (
            <p className="text-meta text-ink-3">
              <span className="rounded-full bg-nested px-[6px] py-[1px]">
                {recommendationLabel}
              </span>{" "}
              {recommended.label}
            </p>
          )}
          {openDecision !== undefined ? (
            <footer className="flex items-center gap-[8px]">
              <Button variant="primary" onClick={openDecision.onOpen}>
                {openDecision.label}
              </Button>
            </footer>
          ) : (
            <footer className="flex items-center gap-[8px]">
              <HumanAction
                verb="Decide"
                actor={actor}
                disabled={busy || value === undefined}
                onClick={onDecide}
              />
              {onRequestMore !== undefined && (
                <Button variant="secondary" opensDialog onClick={onRequestMore} disabled={busy}>
                  {requestMoreLabel}
                </Button>
              )}
            </footer>
          )}
        </>
      )}
      <p className="text-meta text-ink-3">{reservedNote}</p>
    </section>
  );
}
