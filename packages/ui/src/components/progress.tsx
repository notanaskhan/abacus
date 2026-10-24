import clsx from "clsx";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { JSX, ReactNode } from "react";
import { cn } from "../cn";
import { count, progress } from "../format";
import { Icon } from "../icons";
import { useMotion } from "../motion";
import { Reveal } from "./motion";
import { Skeleton } from "./states";
import {
  type BarTone,
  type KpiDelta,
  type KpiTone,
  RING_CIRCUMFERENCE,
  RING_RADIUS,
  SPARK_HEIGHT,
  SPARK_WIDTH,
  type StepInput,
  barView,
  isLongPillLabel,
  kpiDelta,
  ringView,
  sparkPoints,
  stepViews,
} from "./progress-model";
import { Pill } from "./pill";
import { STATE_GEOMETRY } from "./states";
import { StatusDisc } from "./status";

// The Progress kit (C-19; F-05-T19): ProgressBar, RatioStat, UploadRing, StepCounter, KpiTile and
// StatusTile with its strip. DoneCount is in components/pill.tsx (C-06). The rules, from the
// bundle: every bar says "n of N"; espresso or amber, never green (green is only for done); an
// indeterminate bar is for an unknown total only; numbers move only when the count changes, over
// 400ms, and nothing else loops; whole percents; a delta's colour is good or bad, never direction.
// Under reduced motion nothing moves: the width and the offset jump, the indeterminate segment
// sits still, and the tiles do not rise. Colours are tokens.

// ---------------------------------------------------------------------------------------------
// ProgressBar

export interface ProgressBarProps {
  done: number;
  /** Null while the total is unknown: the bar is indeterminate and says so. */
  total: number | null;
  tone?: BarTone;
  /** After "n of N": "files uploaded". Default "complete". */
  noun?: string;
  /** Replaces the left label ("Counting files in the binder…"). */
  left?: string;
  /** In the quiet corner: "Started 20 minutes ago". ink-3, since ink-4 fails AA for text. */
  right?: string;
  still?: boolean;
  className?: string;
}

/**
 * A 3px bar with its "n of N" label on the left and an optional time on the right (C-19 spec 1).
 * The fill is espresso, or amber for uploads and work in flight, and moves over 400ms only when
 * the count changes. An unknown total shows a sliding 30% segment: nothing else is indeterminate.
 */
export function ProgressBar({
  done,
  total,
  tone = "ink",
  noun,
  left,
  right,
  still = false,
  className,
}: ProgressBarProps): JSX.Element {
  const animate = useMotion(still);
  const view = barView(done, total, { noun, left });
  const fill = tone === "amber" ? "bg-amber" : "bg-espresso";
  return (
    <div
      data-tone={tone}
      data-indeterminate={view.indeterminate ? "true" : "false"}
      className={cn("flex items-center gap-[14px] text-dense", className)}
    >
      <span className="shrink-0 whitespace-nowrap text-ink-2">{view.left}</span>
      <div
        role="progressbar"
        {...view.aria}
        className="relative h-[3px] min-w-[40px] flex-1 overflow-hidden rounded-[2px] bg-chip"
      >
        {view.indeterminate ? (
          <span
            data-motion={animate ? "sliding" : "still"}
            className={clsx(
              "absolute top-0 left-0 block h-full w-[30%] rounded-[2px]",
              fill,
              animate && "motion-slide",
            )}
          />
        ) : (
          <span
            className={clsx(
              "block h-full rounded-[2px]",
              fill,
              animate && "transition-[width] duration-400 ease-out",
            )}
            {...(view.width === null ? {} : { style: { width: view.width } })}
          />
        )}
      </div>
      {right !== undefined && (
        <span className="shrink-0 whitespace-nowrap text-ink-3">{right}</span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// RatioStat

export interface RatioStatItem {
  done: number;
  total: number;
  /** "Accounts Reconciled". */
  caption: string;
}

export interface RatioStatProps {
  items: readonly RatioStatItem[];
  className?: string;
}

/**
 * The rail's stat row (C-19 spec 3): a white card of equal columns, each a ratio over its caption.
 * The value is `progress()`, "17% (4 / 24)": a whole percent and the counts it comes from.
 */
export function RatioStat({ items, className }: RatioStatProps): JSX.Element {
  return (
    <div
      className={cn("grid overflow-hidden rounded-pane bg-card shadow-e1", className)}
      style={{ gridTemplateColumns: `repeat(${String(items.length)}, minmax(0, 1fr))` }}
    >
      {items.map((item, i) => (
        <div
          key={item.caption}
          className={cn(
            "flex flex-col gap-[4px] px-[14px] py-[12px]",
            i > 0 && "inset-shadow-hair",
          )}
        >
          <span className="text-title">{progress(item.done, item.total)}</span>
          <span className="text-cell text-ink-3">{item.caption}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// UploadRing

export interface UploadRingProps {
  /** 0 to 1. At 1 the ring gives way to the olive check disc. */
  fraction: number;
  /** "Uploading", "Waiting", "Uploaded". Also the accessible name. */
  caption: string;
  still?: boolean;
}

/**
 * A 50px ring around a file (C-19 spec 4): the amber arc grows over 400ms as the upload does, and
 * at 100% the arc and the file fade out over 180ms and an olive check disc fades in. The arc is
 * hidden at 0, where a round cap would leave a dot.
 */
export function UploadRing({ fraction, caption, still = false }: UploadRingProps): JSX.Element {
  const animate = useMotion(still);
  const view = ringView(fraction);
  const fade = animate ? "transition-opacity duration-[180ms]" : undefined;
  return (
    <div className="flex flex-col items-center gap-[8px]">
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={view.valueNow}
        aria-label={`${caption}, ${view.done ? "uploaded" : "uploading"}`}
        data-done={view.done ? "true" : "false"}
        className="relative flex size-[50px] items-center justify-center"
      >
        <svg
          aria-hidden="true"
          viewBox="0 0 50 50"
          className={cn("absolute inset-0 -rotate-90", fade, view.done && "opacity-0")}
        >
          <circle
            cx={25}
            cy={25}
            r={RING_RADIUS}
            fill="none"
            strokeWidth={2}
            className="stroke-hair"
          />
          {view.arc && (
            <circle
              cx={25}
              cy={25}
              r={RING_RADIUS}
              fill="none"
              strokeWidth={2}
              strokeLinecap="round"
              strokeDasharray={RING_CIRCUMFERENCE}
              strokeDashoffset={view.offset}
              className={clsx(
                "stroke-amber",
                animate && "transition-[stroke-dashoffset] duration-400 ease-out",
              )}
            />
          )}
        </svg>
        <span
          aria-hidden="true"
          className={cn(
            "inline-flex size-[46px] items-center justify-center rounded-pill bg-card text-ink-2 shadow-e1",
            fade,
            view.done && "opacity-0",
          )}
        >
          <Icon name="file" size={18} />
        </span>
        <span
          aria-hidden="true"
          className={cn(
            "absolute top-[2px] left-[2px] inline-flex size-[46px] items-center justify-center rounded-pill bg-green text-on-dark opacity-0 shadow-lift",
            fade,
            view.done && "opacity-100",
          )}
        >
          <Icon name="check" size={20} strokeWidth={2.2} />
        </span>
      </div>
      <span className="text-meta whitespace-nowrap text-ink-3">{caption}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// StepCounter

function StepDisc({ state }: { state: "done" | "progress" | "pending" }): JSX.Element {
  if (state === "done") return <StatusDisc state="done" size={15} />;
  if (state === "pending") {
    return (
      <span
        role="img"
        aria-label="Not started"
        className="size-[15px] shrink-0 rounded-pill inset-ring-[1.3px] inset-ring-ink opacity-40"
      />
    );
  }
  // A 1.5px amber ring on a 30% track with a half arc from 12 o'clock.
  const r = (15 - 1.5) / 2;
  const c = 2 * Math.PI * r;
  return (
    <svg
      role="img"
      aria-label="In progress"
      width={15}
      height={15}
      viewBox="0 0 15 15"
      className="block shrink-0"
    >
      <circle cx={7.5} cy={7.5} r={r} fill="none" strokeWidth={1.5} className="stroke-amber/30" />
      <circle
        cx={7.5}
        cy={7.5}
        r={r}
        fill="none"
        strokeWidth={1.5}
        strokeDasharray={`${String(c / 2)} ${String(c)}`}
        transform="rotate(-90 7.5 7.5)"
        className="stroke-amber"
      />
    </svg>
  );
}

export interface StepCounterProps {
  steps: readonly StepInput[];
  className?: string;
}

/**
 * The steps of an agent run (C-19 spec 5): done is an olive check, the first step still going is
 * amber with a half arc, later ones are rings at 40%. Each row ends in "10 of 312 · 3%", or a dash
 * when the total is not known. "Step", never "task".
 */
export function StepCounter({ steps, className }: StepCounterProps): JSX.Element {
  const views = stepViews(steps);
  return (
    <ul
      aria-label="Agent run steps"
      className={cn("overflow-hidden rounded-pane bg-card shadow-e2", className)}
    >
      {views.map((step) => (
        <li
          key={step.name}
          data-step={step.state}
          className="flex min-h-[40px] items-center gap-[10px] border-t-[0.5px] border-hair px-[14px] first:border-t-0"
        >
          <StepDisc state={step.state} />
          <span
            className={cn(
              "min-w-0 flex-1 truncate text-body",
              step.state === "pending" && "text-ink-3",
            )}
          >
            {step.name}
          </span>
          <span className="shrink-0 text-cell whitespace-nowrap text-ink-3">{step.counter}</span>
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------------------------
// KpiTile

/** Tiles rise 45ms apart on first mount (`--stagger-kpi`). */
export const KPI_STAGGER_MS = 45;

export interface KpiTileProps {
  label: string;
  /** Formatted by the caller through format.ts: "38", "$412,860", "11.4". */
  value: string;
  delta?: { text: string; tone: KpiTone };
  /** The last few readings, drawn as a 76 x 24 line. */
  spark?: readonly number[];
  /** Place in the row, for the stagger. */
  index?: number;
  still?: boolean;
  className?: string;
}

function DeltaLine({ text, view }: { text: string; view: KpiDelta }): JSX.Element {
  return (
    <p
      data-delta={view.judgement}
      className={cn(
        "flex items-center gap-[3px] text-meta",
        view.judgement === "good" && "text-green-ink",
        view.judgement === "bad" && "text-red-ink",
        view.judgement === "flat" && "text-ink-3",
      )}
    >
      {view.arrow === "up" && <ChevronUp aria-hidden="true" size={10} strokeWidth={2} />}
      {view.arrow === "down" && <ChevronDown aria-hidden="true" size={10} strokeWidth={2} />}
      <span>{text}</span>
    </p>
  );
}

/**
 * A Home KPI tile (C-19 spec 6): a label, the value at 20/500, an optional sparkline at the right
 * and a delta line. The arrow says direction; the colour says good or bad, and a flat delta has
 * neither. Tiles stretch to the row's height, so a tile with no sparkline is as tall as its
 * neighbours.
 */
export function KpiTile({
  label,
  value,
  delta,
  spark,
  index = 0,
  still = false,
  className,
}: KpiTileProps): JSX.Element {
  const points = spark === undefined ? "" : sparkPoints(spark);
  return (
    <Reveal
      still={still}
      delay={index * KPI_STAGGER_MS}
      data-kpi="tile"
      className={cn(
        "flex flex-col gap-[5px] rounded-pane bg-card px-[14px] py-[12px] shadow-e1",
        className,
      )}
      style={{ minHeight: STATE_GEOMETRY.card }}
    >
      <p className="text-meta text-ink-3">{label}</p>
      <div className="flex items-end justify-between gap-[10px]">
        <p className="text-dashboard leading-[1.1] font-medium tracking-[-0.015em] whitespace-nowrap">
          {value}
        </p>
        {points !== "" && (
          <svg
            aria-hidden="true"
            width={SPARK_WIDTH}
            height={SPARK_HEIGHT}
            viewBox={`0 0 ${String(SPARK_WIDTH)} ${String(SPARK_HEIGHT)}`}
            className="shrink-0"
          >
            <polyline
              points={points}
              fill="none"
              strokeWidth={1.5}
              strokeLinecap="round"
              strokeLinejoin="round"
              className="stroke-ink-2"
            />
          </svg>
        )}
      </div>
      {delta !== undefined && <DeltaLine text={delta.text} view={kpiDelta(delta.tone)} />}
    </Reveal>
  );
}

/** Up to four tiles across, 10 apart. */
export function KpiGrid({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}): JSX.Element {
  return <div className={cn("grid grid-cols-4 gap-[10px]", className)}>{children}</div>;
}

// ---------------------------------------------------------------------------------------------
// StatusTile

export type StatusTileVariant =
  "neutral" | "state" | "amber" | "red-tint" | "green-tint" | "green" | "muted" | "soon";

const TILE_PILL: Record<
  StatusTileVariant,
  "tag" | "amber" | "red-tint" | "green-tint" | "green" | "muted" | "soon"
> = {
  neutral: "tag",
  state: "amber",
  amber: "amber",
  "red-tint": "red-tint",
  "green-tint": "green-tint",
  green: "green",
  // ENG-01's On hold and Archived tiles (P-07-T27): the muted pill, and the soon pill with Lock 11.
  muted: "muted",
  soon: "soon",
};

export interface StatusTileProps {
  count: number;
  /** The status word, from the registry: "Prepared", "Filed · Accepted". */
  label: string;
  variant?: StatusTileVariant;
  /** A 6px amber dot or a check before the word. */
  mark?: "dot" | "check";
  /** 120 x 72 on the practice strip, 120 x 99 on Home. */
  size?: "practice" | "home";
  /** A tile that filters: pressed while its filter is on. */
  selected?: boolean;
  onSelect?: () => void;
  /** The count is still loading: a skeleton bar holds its place (T1e, ENG-01e). */
  pending?: boolean;
}

/**
 * A status tile (C-19 spec 7): a count over a pill that names the status. The count is `text-kpi`,
 * at most 22px: the plan caps KPI type there, so the Home tile does not take the bundle's 26.
 */
export function StatusTile({
  count: n,
  label,
  variant = "neutral",
  mark,
  size = "practice",
  selected,
  onSelect,
  pending = false,
}: StatusTileProps): JSX.Element {
  const classes = cn(
    "flex w-[120px] flex-col items-center justify-center bg-card shadow-e1",
    size === "home" ? "h-[99px] gap-[10px] rounded-dialog" : "h-[72px] gap-[7px] rounded-pane",
    onSelect !== undefined && "press",
  );
  const long = isLongPillLabel(label);
  const inner = (
    <>
      {pending ? (
        <Skeleton data-tile-count="pending" className="h-[18px] w-[34px]" />
      ) : (
        <span className={cn("text-kpi leading-none", n === 0 && "text-ink-4")}>{count(n)}</span>
      )}
      <Pill
        variant={TILE_PILL[variant]}
        size="state"
        {...(mark === "check" ? { check: true } : {})}
        {...(mark === "dot"
          ? {
              lead: (
                <span aria-hidden="true" className="size-[6px] shrink-0 rounded-pill bg-amber" />
              ),
            }
          : {})}
        className={cn("max-w-[116px] overflow-hidden", long && "gap-[3px] px-[6px] text-micro")}
      >
        {variant === "soon" && <Icon name="lock" size={12} className="flex-none" />}
        <span className="min-w-0 truncate">{label}</span>
      </Pill>
    </>
  );
  if (onSelect !== undefined) {
    return (
      <button
        type="button"
        aria-pressed={selected === true}
        onClick={onSelect}
        data-tile={label}
        className={classes}
      >
        {inner}
      </button>
    );
  }
  return (
    <div data-tile={label} className={classes}>
      {inner}
    </div>
  );
}

export interface StatusTileStripProps {
  /** The group's name for assistive technology: "Tax returns by status". */
  label: string;
  size?: "practice" | "home";
  /** The totals beside the tiles: "79 open · 145 done · 224 TY2025 returns · 161 extended". */
  side?: string;
  /** Under the row, on Home: "Tax returns · TY2025 · 79 open". */
  caption?: string;
  children: ReactNode;
  className?: string;
}

/**
 * A strip of StatusTile (C-19 spec 7): eight on the practice list, four on Home, 10 apart,
 * wrapping. The totals sit after the last tile; the counts must add up (the caller computes them
 * with `practiceOpen`, so a tile never counts itself out).
 */
export function StatusTileStrip({
  label,
  side,
  caption,
  children,
  className,
}: StatusTileStripProps): JSX.Element {
  return (
    <div role="group" aria-label={label} className={cn("flex flex-col gap-[10px]", className)}>
      <div className="flex flex-wrap items-center gap-[10px]">
        {children}
        {side !== undefined && (
          <p className="ml-[6px] text-dense leading-[1.45] text-ink-2">{side}</p>
        )}
      </div>
      {caption !== undefined && <p className="text-cell text-ink-3">{caption}</p>}
    </div>
  );
}
