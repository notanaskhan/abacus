import { Pill, cn } from "@abacus/ui";
import type { JSX } from "react";
import { FIELDWORK_COPY } from "./copy";

// SsarsRail (A-08-T26; AUD-26 b, c): the review, compilation and preparation rails by engagement
// type. The mode comes from the engagement (never chosen here); review mode lists no risk
// register, sampling, confirmations or control testing (AUD-26 acceptance), which the caller's
// steps already leave out.

export type SsarsMode = "review" | "compilation" | "preparation";

export interface SsarsStep {
  key: string;
  label: string;
  state: "done" | "in_progress" | "not_started";
  meta?: string | undefined;
}

export function SsarsRail({
  mode,
  steps,
}: {
  mode: SsarsMode;
  steps: readonly SsarsStep[];
}): JSX.Element {
  const S = FIELDWORK_COPY.ssars;
  return (
    <nav
      aria-label={S.rail}
      data-fieldwork="ssars-rail"
      data-mode={mode}
      className="flex w-[330px] flex-col rounded-pane bg-card shadow-e1"
    >
      <header className="flex h-[40px] items-center gap-[8px] px-[14px] hairline-b">
        <h3 className="text-[13px] font-medium">{S.rail}</h3>
        <Pill variant="neutral" className="ml-auto">
          {S.modes[mode]}
        </Pill>
      </header>
      <ol>
        {steps.map((s) => (
          <li
            key={s.key}
            data-step={s.key}
            data-state={s.state}
            className="flex h-[36px] items-center gap-[10px] px-[14px] text-cell hairline-b"
          >
            <span
              aria-hidden="true"
              className={cn(
                "size-[10px] rounded-full",
                s.state === "done" && "bg-green",
                s.state === "in_progress" &&
                  "bg-[linear-gradient(90deg,var(--color-ink-2)_50%,transparent_50%)] inset-ring-[1px] inset-ring-ink-2",
                s.state === "not_started" && "inset-ring-[1px] inset-ring-ink-3",
              )}
            />
            <span className="flex-1">{s.label}</span>
            {s.meta !== undefined && <span className="text-[11.5px] text-ink-3">{s.meta}</span>}
          </li>
        ))}
      </ol>
    </nav>
  );
}
