import type { JSX } from "react";
import { cn } from "../cn";

// A citation chip (TASK-101/110, the plan's C-31): a small numbered mark beside a claim. A
// verified one opens the source at the cited place; an unverified one says so and opens nothing.
export function CitationChip({
  n,
  label,
  verified,
  onOpen,
}: {
  n: number;
  /** Where it points, for assistive technology and the tooltip ("cell C9", "page 2"). */
  label: string;
  verified: boolean;
  onOpen?: () => void;
}): JSX.Element {
  const title = verified ? `Open the source at ${label}` : `Not verified: ${label}`;
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      disabled={!verified || onOpen === undefined}
      onClick={onOpen}
      className={cn(
        "inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-[5px] px-1 text-[10.5px] font-medium tabular-nums transition-colors",
        verified
          ? "bg-match-bg text-match-ink hover:inset-shadow-[inset_0_0_0_1px_var(--color-match-line)] disabled:cursor-default"
          : "bg-red-tint text-red-ink line-through",
      )}
    >
      {n}
    </button>
  );
}
