import { Check, ChevronDown } from "lucide-react";
import type { HTMLAttributes, JSX, ReactNode } from "react";
import { cn } from "../cn";
import { count } from "../format";
import type { PillSize, PillVariant } from "../status";

// The Pill family (C-06; F-05-T14): Pill is the base every status draws on, and Count, Tag,
// DoneCount and CheckPill are its marks. StatusPill, Tick and the sync chip (components/status.tsx)
// build on it. A pill is radius 999 (`rounded-pill`, DEC-124), 500 weight, one line, no uppercase,
// and holds no icon but the check and the 10px spinner (the bundle's "no icons inside pills").
// Words plus colour, never colour alone.
//
// The ink follows the AA ladder (DEC-11), so `muted` and `soon` are ink-3 where the bundle has .54
// and .30; see tokens/DECISIONS.md, "Buttons and pills".

// ---- Variants ---------------------------------------------------------------------------------

// The colours of each variant, all tokens.
export const PILL_VARIANT: Record<PillVariant, string> = {
  amber: "bg-amber-tint text-amber-ink",
  green: "bg-green text-on-dark shadow-lift",
  "green-tint": "bg-green-tint text-green-ink",
  red: "bg-red text-on-dark shadow-lift",
  "red-tint": "bg-red-tint text-red-ink",
  neutral: "bg-chip text-ink-2",
  muted: "bg-nested font-normal text-ink-3 inset-shadow-hair",
  soon: "bg-nested text-ink-3",
  outline: "bg-card text-ink-2 shadow-e1",
  tag: "bg-nested text-ink-2 inset-shadow-hair",
};

export const PILL_VARIANTS = Object.keys(PILL_VARIANT) as readonly PillVariant[];

// ---- Sizes ------------------------------------------------------------------------------------

interface SizeSpec {
  /** Height, padding and type role. */
  box: string;
  /** The check icon: size and stroke. */
  check: readonly [number, number];
}

// Height, padding and type role per kit size. The type roles carry the font size, the letter
// spacing (-0.005em above 11.5px) and weight 500; the base never sets them. Padding is written in
// px: the root font size is 14px, so Tailwind's numeric spacing (`px-2`) is not pixels.
export const PILL_SIZE: Record<PillSize, SizeSpec> = {
  state: { box: "gap-[4px] h-[21px] px-[8px] text-pill", check: [11, 2.4] },
  "card-state": { box: "gap-[4px] h-[21px] px-[9px] text-pill-card", check: [10, 2.4] },
  sm: { box: "gap-[4px] h-[19px] px-[8px] text-pill-sm", check: [10, 2.4] },
  micro: { box: "h-[18px] gap-[3px] pr-[6px] pl-[5px] text-micro", check: [9, 2.8] },
  status: {
    box: "gap-[4px] h-[25px] pr-[11px] pl-[13px] text-dense font-medium",
    check: [11, 2.4],
  },
  outline: { box: "gap-[4px] h-[22px] px-[9px] text-pill-card", check: [10, 2.4] },
  tally: { box: "gap-[4px] h-[17px] px-[6px] text-micro", check: [9, 2.8] },
  tag: { box: "gap-[4px] h-[23px] px-[9px] text-pill-card", check: [10, 2.4] },
  count: {
    box: "gap-[4px] h-[19px] min-w-[19px] justify-center px-[5px] text-count",
    check: [10, 2.4],
  },
  done: { box: "gap-[4px] h-[21px] px-[8px] text-pill-card", check: [10, 2.4] },
  check: { box: "h-[21px] gap-[3px] pr-[7px] pl-[5px] text-pill-sm", check: [11, 2.2] },
  chip: { box: "h-[29px] gap-[6px] pr-[9px] pl-[8px] text-body font-normal", check: [10, 2.4] },
};

export const PILL_SIZES = Object.keys(PILL_SIZE) as readonly PillSize[];

const PILL_BASE = "inline-flex items-center rounded-pill whitespace-nowrap";

/** The classes of a pill: the base, the variant's colours and the size. The sync chip's word is
 * ink, not the outline variant's ink-2 (C-06 `chip`). A caller's class overrides the kit's (cn). */
export function pillClasses(variant: PillVariant, size: PillSize, className?: string): string {
  const colours =
    size === "chip"
      ? PILL_VARIANT[variant].replace("text-ink-2", "text-ink")
      : PILL_VARIANT[variant];
  return cn(PILL_BASE, colours, PILL_SIZE[size].box, className);
}

// ---- The ring ---------------------------------------------------------------------------------

/** A ring that turns: ink arc on a faint track, 820ms a turn. Under reduced motion the turn is
 * cut to one frame (motion.css); the ring stays drawn. */
export function Ring({
  size,
  width,
  track,
  rotate = 0,
  className,
}: {
  size: number;
  width: number;
  track: string;
  rotate?: number;
  className?: string;
}): JSX.Element {
  const r = (size - width) / 2;
  const c = size / 2;
  const circumference = 2 * Math.PI * r;
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox={`0 0 ${String(size)} ${String(size)}`}
      className={cn("block shrink-0 motion-spin", className)}
    >
      <circle cx={c} cy={c} r={r} fill="none" className={track} strokeWidth={width} />
      <circle
        cx={c}
        cy={c}
        r={r}
        fill="none"
        stroke="currentColor"
        strokeWidth={width}
        strokeLinecap="round"
        strokeDasharray={`${String(circumference * 0.28)} ${String(circumference)}`}
        transform={`rotate(${String(rotate)} ${String(c)} ${String(c)})`}
      />
    </svg>
  );
}

// ---- Pill -------------------------------------------------------------------------------------

export interface PillProps extends Omit<HTMLAttributes<HTMLSpanElement>, "children"> {
  /** A pill variant. Purple `match` is source tracing and is never a status. */
  variant?: PillVariant;
  size?: PillSize;
  /** A check before the label: a finished state. */
  check?: boolean;
  /** The 10px spinner before the label: work in flight. */
  spin?: boolean;
  /** The picker's chevron (the `status` and `chip` sizes have one unless this is false). */
  chevron?: boolean;
  /** Something before the label that is neither the check nor the spinner (the sync chip's glyph). */
  lead?: ReactNode;
  /** The word is bold (a material weakness). */
  bold?: boolean;
  /** The word. One to three words, no uppercase. */
  children?: ReactNode;
}

/** The pill's contents: a check, a spinner or a lead, then the word, then a chevron. */
export function PillBody({
  size,
  check,
  spin,
  chevron,
  lead,
  children,
}: {
  size: PillSize;
  check?: boolean | undefined;
  spin?: boolean | undefined;
  chevron?: boolean | undefined;
  lead?: ReactNode;
  children?: ReactNode;
}): JSX.Element {
  const [checkSize, checkStroke] = PILL_SIZE[size].check;
  const showChevron = chevron ?? (size === "status" || size === "chip");
  return (
    <>
      {check === true && (
        <Check
          aria-hidden="true"
          size={checkSize}
          strokeWidth={checkStroke}
          className="shrink-0"
        />
      )}
      {spin === true && <Ring size={10} width={1.4} track="stroke-rule" />}
      {lead}
      {children}
      {showChevron && (
        <ChevronDown
          aria-hidden="true"
          size={12}
          className={cn("shrink-0", size === "chip" ? "text-ink-3" : "opacity-55")}
        />
      )}
    </>
  );
}

/** A word on a variant's colours at one of the kit's sizes (C-06). The base every status pill,
 * count, tag, tick and done-count draws on. */
export function Pill({
  variant = "neutral",
  size = "state",
  check,
  spin,
  chevron,
  lead,
  bold,
  className,
  children,
  ...props
}: PillProps): JSX.Element {
  return (
    <span
      className={pillClasses(variant, size, cn(bold === true && "font-medium", className))}
      {...props}
    >
      <PillBody size={size} check={check} spin={spin} chevron={chevron} lead={lead}>
        {children}
      </PillBody>
    </span>
  );
}

// ---- Marks ------------------------------------------------------------------------------------

/** How a count reads: plain, bad (something is wrong in it), or inside a Segmented option. */
export type CountTone = "default" | "bad" | "segment";

const COUNT_TONE: Record<CountTone, string> = {
  default: "",
  bad: "bg-red-tint text-red-ink",
  // The bundle's #D7D5CE / #7C746F; the ink is ink-2 because #7C746F is 3.1:1 on that fill.
  segment: "bg-surface-deep text-ink-2",
};

export interface CountProps extends Omit<HTMLAttributes<HTMLSpanElement>, "children"> {
  /** The number. Shown with thousands separators (format.ts). */
  value: number;
  tone?: CountTone;
}

/** A number on a tab or a header (C-06): 19 high, 19 wide at least, centred. */
export function Count({ value, tone = "default", className, ...props }: CountProps): JSX.Element {
  return (
    <Pill size="count" className={cn(COUNT_TONE[tone], className)} data-tone={tone} {...props}>
      {count(value)}
    </Pill>
  );
}

export interface TagProps extends Omit<HTMLAttributes<HTMLSpanElement>, "children"> {
  children: ReactNode;
}

/** A category, never a state (C-06): "Tax Review", "ERP". 23 high on the nested fill and a hair. */
export function Tag({ className, children, ...props }: TagProps): JSX.Element {
  return (
    <Pill variant="tag" size="tag" className={className} {...props}>
      {children}
    </Pill>
  );
}

export interface DoneCountProps extends Omit<HTMLAttributes<HTMLSpanElement>, "children"> {
  done: number;
  total: number;
}

/** Done of total on a task group's header (C-06): complete is "5 of 5" and a check on solid
 * green, partial is "4 of 5" and a turning ring on neutral, none done is neutral and bare. */
export function DoneCount({ done, total, className, ...props }: DoneCountProps): JSX.Element {
  const full = total > 0 && done >= total;
  const partial = !full && done > 0;
  return (
    <Pill
      variant={full ? "green" : "neutral"}
      size="done"
      className={className}
      data-state={full ? "complete" : partial ? "partial" : "none"}
      {...props}
    >
      {`${count(done)} of ${count(total)}`}
      {full && <Check aria-hidden="true" size={10} strokeWidth={2.4} className="shrink-0" />}
      {partial && <Ring size={10} width={1.4} track="stroke-rule" />}
    </Pill>
  );
}

export interface CheckPillProps extends Omit<HTMLAttributes<HTMLSpanElement>, "children"> {
  /** Approved at this level of the tree. */
  approved: boolean;
  /** How many are approved below. Shown only when approved. */
  count?: number;
}

/** The document-level check on a tax review tree row (C-06). White, 21 high, on e1. Approved is an
 * ink check and an ink-2 count ("1"), unapproved is a bare ink-3 check in a 21-square pill.
 * Never a green fill and never green text: green means matched to source. */
export function CheckPill({
  approved,
  count: n,
  className,
  ...props
}: CheckPillProps): JSX.Element {
  if (!approved) {
    return (
      <Pill
        variant="outline"
        size="check"
        role="img"
        aria-label="Not approved"
        className={cn("w-[21px] justify-center p-0", className)}
        data-state="unapproved"
        {...props}
      >
        <Check aria-hidden="true" size={11} strokeWidth={2.2} className="shrink-0 text-ink-3" />
      </Pill>
    );
  }
  return (
    <Pill variant="outline" size="check" className={className} data-state="approved" {...props}>
      <Check aria-hidden="true" size={11} strokeWidth={2.2} className="shrink-0 text-ink" />
      <span className="sr-only">Approved</span>
      {n !== undefined && count(n)}
    </Pill>
  );
}
