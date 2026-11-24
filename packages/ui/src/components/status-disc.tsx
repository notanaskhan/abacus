import { Check, TriangleAlert, X } from "lucide-react";
import type { JSX } from "react";
import { cn } from "../cn";
import { DISC_LABEL, type DiscSize, type DiscState } from "../disc";
import { Ring } from "./pill";

// ---- Discs (C-06) -------------------------------------------------------------------------------------

const DISC_BOX: Record<DiscSize, string> = {
  13: "size-[13px]",
  15: "size-[15px]",
  16: "size-[16px]",
  17: "size-[17px]",
};

/** The glyph inside a disc: 8 at 13 and under, 9 at 15 and 16, 10 at 17. */
function discGlyphSize(size: DiscSize): number {
  if (size >= 17) return 10;
  return size <= 13 ? 8 : 9;
}

export interface StatusDiscProps {
  state: DiscState;
  /** 13 in issue rows, 15 in rows and rails (the default), 17 in task rows. */
  size?: DiscSize;
  className?: string;
}

/** A status disc (C-06): nine states, always next to words, in one left-aligned column. */
export function StatusDisc({ state, size = 15, className }: StatusDiscProps): JSX.Element {
  const glyph = discGlyphSize(size);
  const label = DISC_LABEL[state];
  const box = cn("inline-flex shrink-0 items-center justify-center", DISC_BOX[size], className);
  const round = cn(box, "rounded-full");
  switch (state) {
    case "done":
      return (
        <span role="img" aria-label={label} className={cn(round, "bg-green text-on-dark")}>
          <Check aria-hidden="true" size={glyph} strokeWidth={1.9} />
        </span>
      );
    case "prepared":
      return (
        <span
          role="img"
          aria-label={label}
          className={cn(round, "text-ink-3 inset-ring-[1.3px] inset-ring-ink-4")}
        >
          <Check aria-hidden="true" size={glyph} strokeWidth={1.9} />
        </span>
      );
    case "todo":
      return (
        <span
          role="img"
          aria-label={label}
          className={cn(round, "inset-ring-[1.3px] inset-ring-ink-4")}
        />
      );
    case "half": {
      const mid = size / 2;
      return (
        <span role="img" aria-label={label} className={box}>
          <svg
            aria-hidden="true"
            width={size}
            height={size}
            viewBox={`0 0 ${String(size)} ${String(size)}`}
          >
            <path
              d={`M ${String(mid)} 0 A ${String(mid)} ${String(mid)} 0 0 0 ${String(mid)} ${String(size)} Z`}
              className="fill-ink"
            />
            <circle
              cx={mid}
              cy={mid}
              r={(size - 1.4) / 2}
              fill="none"
              className="stroke-ink-2"
              strokeWidth={1.4}
            />
          </svg>
        </span>
      );
    }
    case "run":
      return (
        <span role="img" aria-label={label} className={box}>
          <Ring size={size} width={1.5} track="stroke-chip" rotate={-140} className="text-ink-2" />
        </span>
      );
    case "warn":
      return (
        <span role="img" aria-label={label} className={cn(box, "text-amber")}>
          <TriangleAlert aria-hidden="true" size={size} strokeWidth={2} />
        </span>
      );
    case "fail":
      return (
        <span role="img" aria-label={label} className={cn(round, "bg-red text-on-dark")}>
          <X aria-hidden="true" size={glyph} strokeWidth={1.9} />
        </span>
      );
    case "off":
      return (
        <span role="img" aria-label={label} className={cn(round, "bg-ink-4 text-on-dark")}>
          <X aria-hidden="true" size={glyph} strokeWidth={1.9} />
        </span>
      );
    case "wait":
      return <span role="img" aria-label={label} className={cn(round, "bg-amber")} />;
  }
}
