import type { JSX } from "react";
import { cn } from "../cn";

// A numbered citation (TASK-101/110): a small mark beside a claim in the legacy screens. A verified
// one opens the source at the cited place; an unverified one says so and opens nothing. The C-07
// kit's CiteMarker and CitationChip (F-05-T41) live in tracing/ and replace it screen by screen.
export function NumberedCitation({
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
        "inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-prop px-1 text-micro tabular-nums transition-colors",
        verified
          ? "bg-match-bg text-match-ink hover:inset-shadow-[inset_0_0_0_1px_var(--color-match-line)] disabled:cursor-default"
          : "bg-red-tint text-red-ink line-through",
      )}
    >
      {n}
    </button>
  );
}
