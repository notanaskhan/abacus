import clsx from "clsx";
import { type CSSProperties, type HTMLAttributes, type JSX, type ReactNode } from "react";
import { useMotion } from "../motion";

// Motion primitives (F-05-T14): Spinner, Pulse, Reveal and TypingDots, from Foundations 04
// (820 ms spinner, 260 ms reveal), C-20 States (the pulse and the live dot), C-26 (the 10px chip
// spinner) and C-10 Chat (the typing dots). Every one asks useMotion() and, under the system
// preference for reduced motion, renders no animation class at all, so document.getAnimations()
// stays empty (SPEC-048 AC-8). `still` forces that same form for a specimen or a test.
//
// Class merging uses clsx, not cn: tailwind-merge reads the type roles as colours (DECISIONS.md,
// "Class merging in the kit").

interface Stillable {
  /** Draw the reduced-motion form whatever the preference: no animation, same size and place. */
  still?: boolean;
}

// ---------------------------------------------------------------------------------------------
// Spinner

export const SPINNER_SIZES = [10, 12, 15] as const;
export type SpinnerSize = (typeof SPINNER_SIZES)[number];

export interface SpinnerProps extends Stillable {
  /** What is happening: "Loading…". Always the accessible name; shown beside the ring by default. */
  label: string;
  /** 10 in a pill or chip (C-26), 12 in a 28px control, 15 as a disc (C-06, C-20). */
  size?: SpinnerSize;
  /** False keeps the label for assistive technology only. */
  showLabel?: boolean;
  className?: string;
}

/**
 * An arc spinner: a faint track, an arc of 28% of the circumference in the current colour, round
 * cap, 1.5 stroke, one turn in 820 ms linear. Under reduced motion the arc stays where it starts
 * and the label carries the state.
 */
export function Spinner({
  label,
  size = 15,
  showLabel = true,
  still = false,
  className,
}: SpinnerProps): JSX.Element {
  const animate = useMotion(still);
  const width = size === 10 ? 1.4 : 1.5;
  const r = (size - width) / 2;
  const c = size / 2;
  const circumference = 2 * Math.PI * r;
  return (
    <span
      role="status"
      data-spinner={animate ? "turning" : "still"}
      className={clsx(
        "inline-flex items-center gap-2 text-ink-2",
        showLabel && "text-dense",
        className,
      )}
    >
      <svg
        aria-hidden="true"
        focusable="false"
        width={size}
        height={size}
        viewBox={`0 0 ${String(size)} ${String(size)}`}
        className={clsx("block shrink-0", animate && "motion-spin")}
      >
        <circle cx={c} cy={c} r={r} fill="none" className="stroke-rule" strokeWidth={width} />
        <circle
          cx={c}
          cy={c}
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth={width}
          strokeLinecap="round"
          strokeDasharray={`${String(circumference * 0.28)} ${String(circumference)}`}
        />
      </svg>
      <span className={showLabel ? undefined : "sr-only"}>{label}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------------------------
// Pulse

/** One row after the last in a skeleton: 70 ms (C-20). */
export const PULSE_STAGGER_MS = 70;

export interface PulseProps extends HTMLAttributes<HTMLDivElement>, Stillable {
  /**
   * `skeleton`: opacity 1, .55, 1 over 1.2 s, for loading bars. `breathe`: opacity 1, .35, 1 over
   * 2.4 s, for the live dot. Never a shimmer gradient (C-20).
   */
  rhythm?: "skeleton" | "breathe";
  /** The row's place in a list; each row starts 70 ms after the one before. */
  index?: number;
  /** Extra delay in milliseconds before the first beat. */
  delay?: number;
  children?: ReactNode;
}

/** A wrapper that pulses what it holds. It is decoration: a loading region sets `aria-busy` itself. */
export function Pulse({
  rhythm = "skeleton",
  index = 0,
  delay = 0,
  still = false,
  className,
  style,
  children,
  ...rest
}: PulseProps): JSX.Element {
  const animate = useMotion(still);
  const offset = index * PULSE_STAGGER_MS + delay;
  const timing: CSSProperties | undefined =
    animate && offset > 0 ? { animationDelay: `${String(offset)}ms` } : undefined;
  return (
    <div
      data-pulse={animate ? rhythm : "still"}
      className={clsx(
        animate && (rhythm === "skeleton" ? "motion-pulse" : "motion-breathe"),
        className,
      )}
      style={{ ...timing, ...style }}
      {...rest}
    >
      {children}
    </div>
  );
}

export interface LiveDotProps extends Stillable {
  className?: string;
}

/**
 * The 8px olive dot in a pane header while anything in the pane runs (C-20). It breathes; it is
 * decoration, so the running state is also said in words next to it.
 */
export function LiveDot({ still = false, className }: LiveDotProps): JSX.Element {
  return (
    <Pulse rhythm="breathe" still={still} aria-hidden="true" className="inline-flex shrink-0">
      <span className={clsx("block size-[8px] rounded-pill bg-green", className)} />
    </Pulse>
  );
}

// ---------------------------------------------------------------------------------------------
// Reveal

export interface RevealProps extends HTMLAttributes<HTMLElement>, Stillable {
  as?: "div" | "span" | "li";
  /** Milliseconds to wait: a table or file row reveals after the paragraph before it (C-10). */
  delay?: number;
  children?: ReactNode;
}

/** What enters the thread or a list: opacity from 0 and a 6px rise over 260 ms. At once under reduced motion. */
export function Reveal({
  as: Tag = "div",
  delay = 0,
  still = false,
  className,
  style,
  children,
  ...rest
}: RevealProps): JSX.Element {
  const animate = useMotion(still);
  const timing: CSSProperties | undefined =
    animate && delay > 0 ? { animationDelay: `${String(delay)}ms` } : undefined;
  return (
    <Tag
      data-reveal={animate ? "rising" : "still"}
      className={clsx(animate && "motion-reveal", className)}
      style={{ ...timing, ...style }}
      {...rest}
    >
      {children}
    </Tag>
  );
}

// ---------------------------------------------------------------------------------------------
// TypingDots

const DOT_STAGGER_MS = 150;

export interface TypingDotsProps extends Stillable {
  /** Says who is typing, for assistive technology: the dots themselves carry no words. */
  label: string;
  /** False draws the three dots without the 39px white bubble. */
  bubble?: boolean;
  className?: string;
}

/** Three 5px ink-3 dots, 1.1 s a beat, 150 ms apart, in the chat's 39px white bubble (C-10). */
export function TypingDots({
  label,
  bubble = true,
  still = false,
  className,
}: TypingDotsProps): JSX.Element {
  const animate = useMotion(still);
  return (
    <span
      role="status"
      data-typing={animate ? "beating" : "still"}
      className={clsx(
        "inline-flex items-center gap-[4px]",
        bubble && "h-[39px] rounded-dialog bg-card px-[14px] shadow-e1",
        className,
      )}
    >
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          aria-hidden="true"
          className={clsx("block size-[5px] rounded-pill bg-ink-3", animate && "motion-typing")}
          style={
            animate && i > 0 ? { animationDelay: `${String(i * DOT_STAGGER_MS)}ms` } : undefined
          }
        />
      ))}
      <span className="sr-only">{label}</span>
    </span>
  );
}
