import { type JSX, type KeyboardEvent, useRef, useState } from "react";
import { cn } from "../cn";
import { devAssert } from "../dev";
import { type ForceState, forceAttr } from "../force-state";
import { Icon, type IconName } from "../icons";
import { PRESS } from "./control-classes";
import { Count } from "./pill";
import { Menu } from "./popover";

// The C-05 Tabs kit (F-05-T15): Segmented, SegmentedGroup, UnderlineTabs, SheetTabs and ViewToggle.
// Every tab control in the app is one of these. They share one keyboard model: `role="tablist"`
// with `role="tab"` options, `aria-selected`, a roving tabindex (only the selected tab is in the
// tab order), and arrows (all four) that move and select, wrapping at the ends and skipping
// disabled options, with Home and End jumping to the first and last enabled tab. The selected
// option switches in place: no sliding indicator, no coloured tab. Controls are pills (DEC-124).
//
// Ink is the AA ladder's (DEC-11): an inactive label is `ink-2`, not the bundle's #7C746F. Focus is
// the global outline (`base.css`), not the bundle's box-shadow ring. See tokens/DECISIONS.md,
// "Inputs and tabs (F-05-T15)".

// ---- Options and the keyboard model -------------------------------------------------------------

export interface TabOption {
  label: string;
  /** A number beside the label, in a count badge. */
  count?: number;
  /** The count is a problem (issues): red tint. */
  bad?: boolean;
  disabled?: boolean;
  /** A registry icon before the label (SheetTabs). */
  icon?: IconName;
  /** The id of the panel this tab controls (`aria-controls`). */
  controls?: string;
}

/** A tab is its label alone, or an object. */
export type Opt = string | TabOption;

/** At most seven options a track (C-05 do and don't). */
export const MAX_OPTIONS_PER_TRACK = 7;

export function tabOption(opt: Opt): TabOption {
  return typeof opt === "string" ? { label: opt } : opt;
}

/**
 * The roving-tabindex keyboard model every tablist shares (the bundle's `nextTab`). Given the key
 * pressed, the index it was pressed on and which options are disabled, it returns the index to
 * select, or -1 when the key means nothing or there is nowhere to go. Arrows wrap and skip the
 * disabled; Home and End go to the first and last enabled option.
 */
export function nextTab(key: string, i: number, disabled: readonly boolean[]): number {
  const n = disabled.length;
  const ok = (j: number): boolean => j >= 0 && j < n && disabled[j] !== true;
  if (key === "Home") {
    let j = 0;
    while (j < n && !ok(j)) j++;
    return ok(j) ? j : -1;
  }
  if (key === "End") {
    let j = n - 1;
    while (j >= 0 && !ok(j)) j--;
    return ok(j) ? j : -1;
  }
  const d =
    key === "ArrowRight" || key === "ArrowDown"
      ? 1
      : key === "ArrowLeft" || key === "ArrowUp"
        ? -1
        : 0;
  if (d === 0) return -1;
  let j = i;
  for (let s = 0; s < n; s++) {
    j = (j + d + n) % n;
    if (ok(j)) return j;
  }
  return -1;
}

/** The states a specimen can hold a tab in. */
export type TabForceState = Extract<ForceState, "hover" | "focus" | "pressed">;

interface Selection {
  /** The selected label (the first enabled option when none is). */
  current: string | undefined;
  select: (label: string) => void;
}

// The selected label is held here and reset when `active` changes from outside (C-05: an external
// change resets the internal selection). `onChange` fires once per change: selecting the tab that
// is already selected does nothing.
function useSelection(
  options: readonly TabOption[],
  active: string | undefined,
  onChange: ((label: string) => void) | undefined,
): Selection {
  const [state, setState] = useState<{ seen: string | undefined; label: string | undefined }>({
    seen: active,
    label: active,
  });
  let label = state.label;
  if (state.seen !== active) {
    label = active;
    setState({ seen: active, label: active });
  }
  const valid = options.find((o) => o.label === label && o.disabled !== true);
  const current = valid?.label ?? options.find((o) => o.disabled !== true)?.label;
  return {
    current,
    select: (next) => {
      if (next === current) return;
      setState({ seen: active, label: next });
      onChange?.(next);
    },
  };
}

// ---- The shared tablist -------------------------------------------------------------------------

type Kind = "segmented" | "underline" | "sheet";

interface TablistProps {
  kind: Kind;
  options: readonly Opt[];
  active?: string | undefined;
  size?: "default" | "small";
  label: string;
  onChange?: ((label: string) => void) | undefined;
  forceState?: TabForceState | undefined;
  /** The option a forced state is held on (the first inactive one when unset; the selected
   * one for `focus`). */
  forceOn?: string | undefined;
  className?: string | undefined;
}

const TRACK: Record<Kind, string> = {
  segmented: "inline-flex flex-none gap-[2px] rounded-pill bg-nav-fill forced-edge",
  underline: "flex items-stretch gap-[4px] px-[2px] hairline-b",
  sheet: "inline-flex items-center gap-[4px]",
};

const TRACK_PAD = { default: "p-[4px]", small: "p-[3px]" } as const;

// Written out in full for Tailwind. An option is a pill (the row of underline tabs is flat); the
// unselected ones darken on hover, the selected one lifts. The press (scale .985, brightness .97)
// is the shared `pressed` utility; `data-[force=...]` draws a state with no pointer.
const OPTION_BASE =
  "relative inline-flex items-center gap-[7px] whitespace-nowrap select-none disabled:pointer-events-none disabled:text-ink-4";

const SEGMENTED_OPTION = {
  default: "h-[30px] px-[16px] text-tab",
  small: "h-[28px] px-[13px] text-btn",
} as const;
// With a count the right padding tightens: 0 10 0 16 and 0 8 0 13.
const SEGMENTED_COUNT = { default: "pr-[10px]", small: "pr-[8px]" } as const;

function optionClasses(
  kind: Kind,
  size: "default" | "small",
  on: boolean,
  hasCount: boolean,
): string {
  if (kind === "segmented") {
    return cn(
      OPTION_BASE,
      PRESS,
      "rounded-pill",
      SEGMENTED_OPTION[size],
      hasCount && SEGMENTED_COUNT[size],
      on
        ? "cursor-default bg-card font-medium text-ink shadow-e1"
        : "font-normal text-ink-2 hover:bg-sel-bg data-[force=hover]:bg-sel-bg data-[force=pressed]:bg-sel-bg",
    );
  }
  if (kind === "underline") {
    // The 2px underline is a pseudo-element on the row's rule, so the item does not move.
    return cn(
      OPTION_BASE,
      "h-[37px] px-[10px] text-btn transition-colors duration-[180ms]",
      on
        ? "cursor-default font-medium text-ink after:absolute after:inset-x-0 after:bottom-0 after:h-[2px] after:bg-espresso"
        : "font-normal text-ink-2 hover:text-ink data-[force=hover]:text-ink data-[force=pressed]:text-ink",
    );
  }
  return cn(
    OPTION_BASE,
    PRESS,
    "h-[30px] rounded-pill px-[10px] text-btn",
    on
      ? "cursor-default bg-nested font-medium text-ink shadow-e1"
      : "font-normal text-ink-2 hover:bg-nav-fill data-[force=hover]:bg-nav-fill data-[force=pressed]:bg-nav-fill",
  );
}

function Tablist({
  kind,
  options,
  active,
  size = "default",
  label,
  onChange,
  forceState,
  forceOn,
  className,
}: TablistProps): JSX.Element {
  const opts = options.map(tabOption);
  devAssert(
    opts.length <= MAX_OPTIONS_PER_TRACK,
    `A tab track holds at most ${String(MAX_OPTIONS_PER_TRACK)} options (C-05), not ${String(opts.length)}`,
  );
  const { current, select } = useSelection(opts, active, onChange);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const disabled = opts.map((o) => o.disabled === true);
  const forced =
    forceState === undefined
      ? undefined
      : (forceOn ??
        (forceState === "focus"
          ? current
          : opts.find((o) => o.disabled !== true && o.label !== current)?.label));

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number): void => {
    const target = nextTab(event.key, index, disabled);
    if (target < 0) return;
    event.preventDefault();
    const next = opts[target];
    if (next === undefined) return;
    select(next.label);
    tabs.current[target]?.focus();
  };

  return (
    <div
      role="tablist"
      aria-label={label}
      data-kind={kind}
      className={cn(TRACK[kind], kind === "segmented" && TRACK_PAD[size], className)}
    >
      {opts.map((opt, index) => {
        const on = opt.label === current;
        return (
          <button
            key={opt.label}
            ref={(element) => {
              tabs.current[index] = element;
            }}
            type="button"
            role="tab"
            aria-selected={on}
            {...(opt.controls === undefined ? {} : { "aria-controls": opt.controls })}
            tabIndex={on ? 0 : -1}
            disabled={opt.disabled === true}
            className={optionClasses(kind, size, on, opt.count !== undefined)}
            {...(forced === opt.label ? forceAttr(forceState) : {})}
            onClick={() => {
              select(opt.label);
            }}
            onKeyDown={(event) => {
              onKeyDown(event, index);
            }}
          >
            {opt.icon !== undefined && <Icon name={opt.icon} size={14} />}
            {opt.label}
            {opt.count !== undefined && (
              <Count value={opt.count} tone={opt.bad === true ? "bad" : "segment"} />
            )}
          </button>
        );
      })}
    </div>
  );
}

// ---- Segmented ----------------------------------------------------------------------------------

export interface SegmentedProps {
  options: readonly Opt[];
  /** The selected label. A change from outside resets the selection. */
  active?: string;
  /** Default 30 high; small is 28, for pane headers. */
  size?: "default" | "small";
  /** The tablist's accessible name. */
  label: string;
  /** Fires once per change, with the new label. */
  onChange?: (label: string) => void;
  /** Hold one option in a state for a specimen. */
  forceState?: TabForceState;
  forceOn?: string;
  className?: string;
}

/** The primary tab style (C-05): a pill track of options, the selected one white and lifted.
 * Centre it in the tabsbar; small sets go in pane headers. At most seven options. */
export function Segmented(props: SegmentedProps): JSX.Element {
  return <Tablist kind="segmented" {...props} />;
}

// ---- SegmentedGroup -----------------------------------------------------------------------------

export interface SegmentedGroupProps {
  options: readonly Opt[];
  active?: string;
  size?: "default" | "small";
  label: string;
  /** The second track: the sub-navigation of the selected first-track item, shown only when that
   * item has an entry. */
  sub?: Record<string, { options: readonly Opt[]; active?: string }>;
  /** Changing the first track reports that item's current section. */
  onChange?: (item: string, section?: string) => void;
  className?: string;
}

/** Two Segmented tracks 8px apart (C-05): the second follows the selected first-track item and
 * keeps its own selection for each of them. */
export function SegmentedGroup({
  options,
  active,
  size = "default",
  label,
  sub,
  onChange,
  className,
}: SegmentedGroupProps): JSX.Element {
  const first = options.map(tabOption);
  const [item, setItem] = useState<{ seen: string | undefined; label: string | undefined }>({
    seen: active,
    label: active,
  });
  let selected = item.label;
  if (item.seen !== active) {
    selected = active;
    setItem({ seen: active, label: active });
  }
  const current =
    first.find((o) => o.label === selected && o.disabled !== true)?.label ??
    first.find((o) => o.disabled !== true)?.label;
  const [sections, setSections] = useState<Record<string, string>>({});
  const subOf = current === undefined ? undefined : sub?.[current];
  const subOptions = subOf?.options.map(tabOption);
  const section =
    current === undefined
      ? undefined
      : (sections[current] ??
        subOf?.active ??
        subOptions?.find((o) => o.disabled !== true)?.label);

  return (
    <div className={cn("inline-flex max-w-full items-center gap-[8px]", className)}>
      <Tablist
        kind="segmented"
        options={first}
        size={size}
        label={label}
        active={current}
        onChange={(next) => {
          setItem({ seen: active, label: next });
          const nextSub = sub?.[next];
          const nextSection =
            sections[next] ??
            nextSub?.active ??
            nextSub?.options.map(tabOption).find((o) => o.disabled !== true)?.label;
          onChange?.(next, nextSection);
        }}
      />
      {subOf !== undefined && current !== undefined && (
        <Tablist
          // A different first item is a different track, so it starts from its own section.
          key={current}
          kind="segmented"
          options={subOf.options}
          size={size}
          label={`${label}: ${current}`}
          active={section}
          onChange={(next) => {
            setSections((all) => ({ ...all, [current]: next }));
            onChange?.(current, next);
          }}
        />
      )}
    </div>
  );
}

// ---- UnderlineTabs and SheetTabs ----------------------------------------------------------------

export interface UnderlineTabsProps {
  options: readonly Opt[];
  active?: string;
  label: string;
  onChange?: (label: string) => void;
  forceState?: TabForceState;
  forceOn?: string;
  className?: string;
}

/** Settings sections (C-05): 37 high, the selected one ink 500 with a 2px espresso underline on
 * the row's hairline. Never primary navigation. */
export function UnderlineTabs(props: UnderlineTabsProps): JSX.Element {
  return <Tablist kind="underline" {...props} />;
}

export interface SheetTabsProps {
  /** Each with an `icon`: panels-top-left, layers, chart-column. */
  options: readonly Opt[];
  active?: string;
  label: string;
  onChange?: (label: string) => void;
  forceState?: TabForceState;
  forceOn?: string;
  className?: string;
}

/** The workbook sheet switcher in a pane header (C-05): 30 high pills with a leading icon, the
 * selected one on nested with e1. */
export function SheetTabs(props: SheetTabsProps): JSX.Element {
  return <Tablist kind="sheet" {...props} />;
}

// ---- ViewToggle ---------------------------------------------------------------------------------

export interface ViewOption {
  v: string;
  label: string;
  icon: IconName;
}

export const DEFAULT_VIEWS: readonly ViewOption[] = [
  { v: "grid", label: "Grid", icon: "layout-grid" },
  { v: "list", label: "List", icon: "list" },
];

export interface ViewToggleProps {
  /** The current view's `v`. A change from outside resets it. */
  view?: string;
  /** Grid and List unless given. */
  views?: readonly ViewOption[];
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  /** Fires only when the choice changes. */
  onView?: (v: string) => void;
  /** Hold the menu open (`open`) or the button hovered, for a specimen. */
  forceState?: Extract<ForceState, "hover" | "open">;
  className?: string;
}

/** The one grid / list pill (C-05): 29 high, white on e1, the layout-grid icon and a chevron
 * always (the icon does not follow the view). ↓ opens a 176px radio menu and focuses its first
 * item; Escape closes it and returns focus to the button. */
export function ViewToggle({
  view,
  views = DEFAULT_VIEWS,
  open,
  onOpenChange,
  onView,
  forceState,
  className,
}: ViewToggleProps): JSX.Element {
  const [state, setState] = useState<{ seen: string | undefined; v: string | undefined }>({
    seen: view,
    v: view,
  });
  let chosen = state.v;
  if (state.seen !== view) {
    chosen = view;
    setState({ seen: view, v: view });
  }
  const current = views.find((o) => o.v === chosen) ?? views[0];
  const name = current === undefined ? "View" : `View: ${current.label}`;
  return (
    <Menu
      label="View"
      width={176}
      align="end"
      {...(open === undefined ? {} : { open })}
      {...(onOpenChange === undefined ? {} : { onOpenChange })}
      {...(forceState === "open" ? { forceState } : {})}
      sections={[
        views.map((option) => ({
          label: option.label,
          icon: option.icon,
          checked: option.v === current?.v,
          onSelect: () => {
            if (option.v === current?.v) return;
            setState({ seen: view, v: option.v });
            onView?.(option.v);
          },
        })),
      ]}
      trigger={
        <button
          type="button"
          aria-label={name}
          title={name}
          {...(forceState === "hover" ? forceAttr(forceState) : {})}
          className={cn(
            "relative inline-flex h-[29px] items-center gap-[5px] rounded-pill bg-card px-[9px] text-ink-2 shadow-e1 press active:pressed hover:bg-nav-fill data-[force=hover]:bg-nav-fill data-[state=open]:bg-nav-fill",
            className,
          )}
        >
          <Icon name="layout-grid" size={14} />
          <Icon name="chevron-down" size={12} />
        </button>
      }
    />
  );
}
