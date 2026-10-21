import { type JSX, type RefObject, useLayoutEffect, useRef, useState } from "react";
import { cn } from "../cn";
import { PRESS } from "../components/control-classes";
import { Menu, Tooltip } from "../components/popover";
import { Icon } from "../icons";
import {
  type FallbackStage,
  type ToolbarFit,
  type ToolbarMeasure,
  fitToolbar,
} from "./nav-overflow";

// The firm Toolbar (C-00 Shell Kit, SHL-01; F-05-T18): Go... · firm pill · centred text nav ·
// Support · bell. 46 high, white, a hairline under it. It carries no Accrued mark (the firm app
// shows none), no icons and no counts on the nav, and a 6px dot on the bell, never a number.
//
// The nav never wraps and never shrinks its type. A hidden row measures every control at its
// real size (weight 500, so the active item never changes the layout) and `fitToolbar` applies
// the DF-39 fallback order to those widths: short firm name, Home as a house pill, then trailing
// items into "More". It re-measures when the bar resizes, when fonts load and on every render.

/** A nav item. The app owns the list (apps/web/src/shell/nav.ts, 13 areas); the shell only draws it. */
export interface ToolbarNavItem {
  label: string;
}

/** A control a specimen holds in a state with no pointer. */
export interface ToolbarForceState {
  /** Go... held hovered or pressed. */
  go?: "hover" | "pressed";
  /** Show the Go... tooltip (the line under it lists the other ways in). */
  goTip?: boolean;
  /** One nav item held hovered, focused or pressed. */
  nav?: { label: string; state: "hover" | "focus" | "pressed" };
  /** Open the More menu in place. */
  moreOpen?: boolean;
}

export interface ToolbarProps {
  /** The areas, in order. The first is Home: it becomes the house pill under DF-39 step 2. */
  nav: readonly ToolbarNavItem[];
  /** The active area's label. Empty means none (settings screens). */
  active?: string;
  /** The firm's display name ("Brightwater Hale"). */
  firm: string;
  /** The name shown under DF-39 step 1 (the first word of `firm` when not given). */
  firmShort?: string;
  /** The firm's full name, for the pill's hint and accessible name ("Brightwater Hale LLP"). */
  firmTitle?: string;
  /** The firm pill reads as pressed: the settings context, or its menu is open. */
  firmPressed?: boolean;
  supportPressed?: boolean;
  bellPressed?: boolean;
  /** The bell's dot: something is unread. Default true. */
  unread?: boolean;
  /** Hold the toolbar at a fallback step at least this far (the strips that draw fallback 1 or 2). */
  minFallback?: FallbackStage;
  /** `none` keeps every item and control at full size (width tests). */
  overflow?: "auto" | "none";
  onGo?: () => void;
  onNavigate?: (label: string) => void;
  onSupport?: () => void;
  onBell?: () => void;
  onFirm?: () => void;
  /** Hold a control in a state for a specimen. */
  forceState?: ToolbarForceState;
  className?: string;
}

// ---- Classes, written in full so Tailwind sees them -------------------------------------------

const FILL = "bg-nav-fill shadow-e1 hover:bg-sel-bg data-[force=hover]:bg-sel-bg";
const NAV_ITEM = cn(
  "inline-flex h-[32px] flex-none items-center rounded-pill px-[12px] text-nav whitespace-nowrap text-ink-2",
  "hover:bg-sel-bg hover:text-ink data-[force=hover]:bg-sel-bg data-[force=hover]:text-ink",
  "data-[force=pressed]:bg-sel-bg data-[force=pressed]:text-ink",
  "aria-[current=page]:bg-nav-fill aria-[current=page]:font-medium aria-[current=page]:text-ink",
);
// A label measures at weight 500 whatever its weight now: a hidden 500 copy of itself (`after`)
// holds the width, so the active item does not move its neighbours.
const LABEL =
  "inline-flex flex-col after:invisible after:block after:h-0 after:overflow-hidden after:font-medium after:content-[attr(data-label)]";
const GO = cn(
  "inline-flex h-[30px] flex-none items-center gap-[7px] rounded-pill bg-espresso pr-[12px] pl-[10px] text-nav font-normal text-on-dark shadow-e1",
  "hover:bg-cta-hover data-[force=hover]:bg-cta-hover data-[force=pressed]:bg-cta-hover",
);
const FIRM = cn(
  "inline-flex h-[30px] flex-none items-center gap-[6px] rounded-pill pr-[9px] pl-[11px] text-nav text-ink",
  FILL,
  "data-[pressed=true]:bg-sel-bg",
);
const HOUSE = cn(
  "inline-flex size-[30px] flex-none items-center justify-center rounded-pill text-ink",
  FILL,
  "aria-[current=page]:bg-sel-bg",
);
const SUPPORT = cn(
  "inline-flex h-[30px] flex-none items-center gap-[7px] rounded-pill pr-[12px] pl-[10px] text-nav text-ink",
  FILL,
  "aria-pressed:bg-sel-bg",
);
const BELL = cn(
  "group/bell relative inline-flex size-[30px] flex-none items-center justify-center rounded-pill text-ink",
  FILL,
  "aria-pressed:bg-sel-bg",
);
const MORE = cn(
  "inline-flex h-[32px] flex-none items-center gap-[4px] rounded-pill pr-[10px] pl-[12px] text-nav whitespace-nowrap text-ink-2",
  "hover:bg-sel-bg hover:text-ink data-[state=open]:bg-sel-bg data-[state=open]:text-ink",
  "data-[current=true]:bg-nav-fill data-[current=true]:font-medium data-[current=true]:text-ink",
);

function GoContent(): JSX.Element {
  return (
    <>
      <Icon name="search" size={14} />
      <span>Go…</span>
    </>
  );
}

function FirmContent({ label }: { label: string }): JSX.Element {
  return (
    <>
      <span className="max-w-[160px] truncate">{label}</span>
      <Icon name="chevron-down" size={12} className="text-ink-2" />
    </>
  );
}

function SupportContent(): JSX.Element {
  return (
    <>
      <Icon name="message-circle" size={14} filled />
      <span>Support</span>
    </>
  );
}

function MoreContent({ weight }: { weight?: boolean }): JSX.Element {
  return (
    <>
      <span className={cn(weight === true && "font-medium")}>More</span>
      <Icon name="chevron-down" size={12} />
    </>
  );
}

// ---- Measuring --------------------------------------------------------------------------------

function widthOf(bar: HTMLElement, key: string): number {
  const el = bar.querySelector<HTMLElement>(`[data-measure="${key}"]`);
  return el === null ? 0 : el.getBoundingClientRect().width;
}

function readMeasure(bar: HTMLElement, count: number): ToolbarMeasure {
  const items: number[] = [];
  for (let i = 0; i < count; i++) items.push(widthOf(bar, `item:${String(i)}`));
  return {
    barWidth: bar.getBoundingClientRect().width,
    go: widthOf(bar, "go"),
    firm: widthOf(bar, "firm"),
    firmShort: widthOf(bar, "firm-short"),
    homePill: widthOf(bar, "home"),
    support: widthOf(bar, "support"),
    bell: widthOf(bar, "bell"),
    items,
    more: widthOf(bar, "more"),
  };
}

function same(a: ToolbarMeasure | null, b: ToolbarMeasure): boolean {
  return a !== null && JSON.stringify(a) === JSON.stringify(b);
}

/** The bar's measured widths, or null before the first layout. */
function useMeasure(count: number): {
  ref: RefObject<HTMLElement | null>;
  measure: ToolbarMeasure | null;
} {
  const ref = useRef<HTMLElement | null>(null);
  const [measure, setMeasure] = useState<ToolbarMeasure | null>(null);
  const read = (): void => {
    const bar = ref.current;
    if (bar === null) return;
    const next = readMeasure(bar, count);
    setMeasure((prev) => (same(prev, next) ? prev : next));
  };
  // Every render: a label, the firm's name or a control may have changed width.
  useLayoutEffect(read);
  useLayoutEffect(() => {
    const bar = ref.current;
    if (bar === null) return undefined;
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(read);
    observer?.observe(bar);
    // Geist changes every width when it arrives.
    let live = true;
    const fonts = (document as { fonts?: FontFaceSet }).fonts;
    void fonts?.ready.then(() => {
      if (live) read();
    });
    return () => {
      live = false;
      observer?.disconnect();
    };
  }, [count]);
  return { ref, measure };
}

const NOT_MEASURED: ToolbarFit = {
  stage: "none",
  firmShort: false,
  homePill: false,
  inline: Number.POSITIVE_INFINITY,
};

// ---- Toolbar ----------------------------------------------------------------------------------

export function Toolbar({
  nav,
  active = "",
  firm,
  firmShort,
  firmTitle,
  firmPressed = false,
  supportPressed = false,
  bellPressed = false,
  unread = true,
  minFallback = "none",
  overflow = "auto",
  onGo,
  onNavigate,
  onSupport,
  onBell,
  onFirm,
  forceState,
  className,
}: ToolbarProps): JSX.Element {
  const { ref, measure } = useMeasure(nav.length);
  const short = firmShort ?? firm.split(" ")[0] ?? firm;
  const fit =
    measure === null ? NOT_MEASURED : fitToolbar(measure, { min: minFallback, overflow });
  const inline = Math.min(fit.inline, nav.length);
  const home = nav[0];
  const from = fit.homePill ? 1 : 0;
  const shown = nav.slice(from, inline);
  const hidden = nav.slice(inline);
  const activeInMore = hidden.some((item) => item.label === active);
  const forced = (label: string): "hover" | "focus" | "pressed" | undefined =>
    forceState?.nav?.label === label ? forceState.nav.state : undefined;
  const goForce = forceState?.go;
  const firmLabel = fit.firmShort ? short : firm;

  const moreTrigger = (
    <button
      type="button"
      className={cn(MORE, PRESS)}
      data-current={activeInMore ? "true" : undefined}
    >
      <MoreContent />
    </button>
  );

  return (
    <header
      ref={ref}
      data-shell="toolbar"
      data-stage={fit.stage}
      className={cn(
        "relative flex h-(--toolbar-h) w-full flex-none items-center gap-[8px] bg-card px-(--edge-app) text-nav hairline-b",
        className,
      )}
    >
      <div className="flex flex-none items-center gap-[8px]">
        <Tooltip
          content={
            <>
              Go to anything <span className="text-ink-3">⌘K</span>
            </>
          }
          detail="Also: New to-do… · Load saved prompt… · Open board"
          side="bottom"
          {...(forceState?.goTip === true ? { forceState: "open" as const } : {})}
        >
          <button
            type="button"
            aria-label="Go to anything ⌘K"
            className={cn(GO, PRESS)}
            {...(goForce === undefined ? {} : { "data-force": goForce })}
            onClick={onGo}
          >
            <GoContent />
          </button>
        </Tooltip>
        {fit.homePill && home !== undefined && (
          <button
            type="button"
            aria-label={home.label}
            title={home.label}
            {...(active === home.label ? { "aria-current": "page" as const } : {})}
            className={cn(HOUSE, PRESS)}
            onClick={() => onNavigate?.(home.label)}
          >
            <Icon name="house" size={14} />
          </button>
        )}
        <button
          type="button"
          title={firmTitle ?? firm}
          aria-label={firmTitle ?? firm}
          aria-haspopup="menu"
          data-pressed={firmPressed}
          className={cn(FIRM, PRESS)}
          onClick={onFirm}
        >
          <FirmContent label={firmLabel} />
        </button>
      </div>

      <nav
        aria-label="Modules"
        className="flex h-[32px] min-w-0 flex-1 items-center justify-center gap-px"
      >
        {shown.map((item) => {
          const force = forced(item.label);
          return (
            <button
              key={item.label}
              type="button"
              {...(item.label === active ? { "aria-current": "page" as const } : {})}
              {...(force === undefined ? {} : { "data-force": force })}
              className={cn(NAV_ITEM, PRESS)}
              onClick={() => onNavigate?.(item.label)}
            >
              <span data-label={item.label} className={LABEL}>
                {item.label}
              </span>
            </button>
          );
        })}
        {hidden.length > 0 && (
          <Menu
            label="More"
            width={220}
            align="end"
            trigger={moreTrigger}
            {...(forceState?.moreOpen === true ? { forceState: "open" as const } : {})}
            sections={[
              hidden.map((item) => ({
                label: item.label,
                checked: item.label === active,
                onSelect: () => onNavigate?.(item.label),
              })),
            ]}
          />
        )}
      </nav>

      <div className="flex flex-none items-center gap-[8px]">
        <button
          type="button"
          aria-pressed={supportPressed}
          className={cn(SUPPORT, PRESS)}
          onClick={onSupport}
        >
          <SupportContent />
        </button>
        <button
          type="button"
          aria-label={unread ? "Notifications, unread" : "Notifications"}
          aria-pressed={bellPressed}
          className={cn(BELL, PRESS)}
          onClick={onBell}
        >
          <Icon name="bell" size={14} />
          {unread && (
            <span
              aria-hidden="true"
              data-dot="unread"
              className="absolute top-[6px] right-[7px] size-[6px] rounded-full bg-red ring-[1.5px] ring-nav-fill group-hover/bell:ring-sel-bg group-aria-pressed/bell:ring-sel-bg"
            />
          )}
        </button>
      </div>

      <Measuring nav={nav} firm={firm} short={short} />
    </header>
  );
}

/** The hidden row every width is read from: the same classes at their natural size. */
function Measuring({
  nav,
  firm,
  short,
}: {
  nav: readonly ToolbarNavItem[];
  firm: string;
  short: string;
}): JSX.Element {
  const m = (key: string): { "data-measure": string } => ({ "data-measure": key });
  return (
    <div
      aria-hidden="true"
      data-measuring=""
      className="pointer-events-none invisible absolute top-0 left-0 flex h-0 w-max items-center gap-[8px] overflow-hidden"
    >
      <span {...m("go")} className={GO}>
        <GoContent />
      </span>
      <span {...m("firm")} className={FIRM}>
        <FirmContent label={firm} />
      </span>
      <span {...m("firm-short")} className={FIRM}>
        <FirmContent label={short} />
      </span>
      <span {...m("home")} className={HOUSE} />
      <span {...m("support")} className={SUPPORT}>
        <SupportContent />
      </span>
      <span {...m("bell")} className={BELL} />
      <span {...m("more")} className={cn(MORE, "font-medium")}>
        <MoreContent weight />
      </span>
      {nav.map((item, i) => (
        <span key={item.label} {...m(`item:${String(i)}`)} className={cn(NAV_ITEM, "font-medium")}>
          {item.label}
        </span>
      ))}
    </div>
  );
}
