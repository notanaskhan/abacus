import { Check } from "lucide-react";
import type { JSX } from "react";
import { cn } from "../cn";
import { type ForceState, forceAttr } from "../force-state";
import { Icon } from "../icons";

// The two espresso bars of a workpaper (C-02 §2 and §6; F-05-T50). The SectionBand divides a
// workpaper's numbered sections: full bleed, 30 high, padding 0 14, on-dark 12 / 500 +.04em
// uppercase, never rounded, never another colour, never a page header. A collapsible band is one
// native button (aria-expanded, no buttons inside) whose chevron turns −90° in 220ms. The
// ScheduleBar titles a supporting schedule: 28 high, 11.5 / 500. These and a rendered Excel header
// row are the only espresso fills in a workpaper.

export interface SectionBandProps {
  /** "SECTION {number} — {title}" (em dash with spaces; the uppercase is CSS). */
  number?: number;
  title?: string;
  /** Replaces the generated label. */
  label?: string;
  /** The sign-off micro text after a check: "Prepared · Accrued Agent". */
  sign?: string;
  /** Default true: one native button. False: a plain bar with no chevron. */
  collapsible?: boolean;
  /** Controlled: the section is collapsed. */
  collapsed?: boolean;
  onToggle?: (open: boolean) => void;
  /** The id of the content the band shows and hides. */
  controls?: string;
  forceState?: Extract<ForceState, "hover" | "focus">;
  className?: string;
}

/** The band's words: "Section 1 — Service organizations" (drawn uppercase). */
export function bandLabel({
  number,
  title,
  label,
}: Pick<SectionBandProps, "number" | "title" | "label">): string {
  if (label !== undefined) return label;
  return number === undefined ? (title ?? "") : `Section ${String(number)} — ${title ?? ""}`;
}

const BAND =
  "flex h-[30px] w-full flex-none items-center gap-[10px] rounded-none bg-espresso px-[14px] text-left text-band-dark text-on-dark uppercase";

export function SectionBand({
  number,
  title,
  label,
  sign,
  collapsible = true,
  collapsed = false,
  onToggle,
  controls,
  forceState,
  className,
}: SectionBandProps): JSX.Element {
  const text = bandLabel({
    ...(number === undefined ? {} : { number }),
    ...(title === undefined ? {} : { title }),
    ...(label === undefined ? {} : { label }),
  });
  const body = (
    <>
      <span data-band="label" className="min-w-0 flex-1 truncate">
        {text}
      </span>
      {sign !== undefined && (
        <span
          data-band="sign"
          className="inline-flex flex-none items-center gap-[4px] text-pill-sm tracking-normal whitespace-nowrap text-on-dark/72 normal-case"
        >
          <Check aria-hidden="true" size={11} strokeWidth={2} className="shrink-0" />
          {sign}
        </span>
      )}
      {collapsible && (
        <Icon
          name="chevron-down"
          size={12}
          className={cn(
            "flex-none text-on-dark/72 transition-transform duration-[220ms] ease-out",
            collapsed && "-rotate-90",
          )}
        />
      )}
    </>
  );
  if (!collapsible) {
    return (
      <div data-workpaper="band" className={cn(BAND, className)}>
        {body}
      </div>
    );
  }
  return (
    <button
      type="button"
      data-workpaper="band"
      aria-expanded={!collapsed}
      {...(controls === undefined ? {} : { "aria-controls": controls })}
      {...forceAttr(forceState)}
      onClick={() => onToggle?.(collapsed)}
      className={cn(BAND, "cursor-pointer focus-visible:outline-offset-[-2px]", className)}
    >
      {body}
    </button>
  );
}

export interface ScheduleBarProps {
  /** "Schedule 1100.04-A · SOC 1 report coverage". */
  title: string;
  className?: string;
}

/** The supporting-schedule title bar over a section's table. */
export function ScheduleBar({ title, className }: ScheduleBarProps): JSX.Element {
  return (
    <p
      data-workpaper="schedule"
      className={cn(
        "flex h-[28px] flex-none items-center truncate bg-espresso px-[14px] text-meta leading-none font-medium tracking-[-0.005em] whitespace-nowrap text-on-dark",
        className,
      )}
    >
      <span className="min-w-0 truncate">{title}</span>
    </p>
  );
}
