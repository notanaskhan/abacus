import type { JSX } from "react";
import { cn } from "../cn";
import { StatusDisc } from "../components/status";

// ChecksList (E7; P-04-T40): what a gate checks before a person may act, each a disc beside its
// words (never colour alone). A failing check names what to do; the list reads as a group.

export interface GateCheck {
  key: string;
  label: string;
  ok: boolean;
  /** What to do when it fails ("Sign L2 first"). */
  detail?: string;
}

export function ChecksList({
  checks,
  label = "Checks",
  className,
}: {
  checks: readonly GateCheck[];
  label?: string;
  className?: string;
}): JSX.Element {
  return (
    <ul aria-label={label} data-gate="checks" className={cn("flex flex-col gap-[6px]", className)}>
      {checks.map((c) => (
        <li key={c.key} className="flex items-start gap-[8px] text-dense">
          <StatusDisc state={c.ok ? "done" : "fail"} />
          <span className="flex flex-col">
            <span className={cn(!c.ok && "text-red-ink")}>{c.label}</span>
            {!c.ok && c.detail !== undefined && (
              <span className="text-meta text-ink-3">{c.detail}</span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}
