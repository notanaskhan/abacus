import * as DropdownPrimitive from "@radix-ui/react-dropdown-menu";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { Slot } from "@radix-ui/react-slot";
import { type JSX, type ReactNode, createContext, useContext, useId, useState } from "react";
import { cn } from "../cn";
import { assertDialogLabel } from "../dev";
import { Icon, type IconName } from "../icons";
import { useMotion } from "../motion";
import { useOverlayLayer } from "../overlays/stack-react";

// Anchored overlays: a menu and a tooltip (plan 04 section 4.5; F-05-T15; the O1 popover is in
// overlays/popover.tsx). Radix is the behaviour (focus, keyboard, collision, dismissal, focus return); the look is tokens.
//
// The menu is the C-00 and C-05 menu: a nested-greige tray of radius 15 around a white body of
// radius 11, rows 34 high, radius 8, hover and focus on nav-fill, a 260ms reveal. A section whose
// items carry `checked` is a radio group (`role="menuitemradio"`, a check on the current one); the
// picker, the view toggle and the value rows use it. The tooltip is the C-00 white one: radius 10,
// 12.5 ink with an optional 11.5 ink-3 second line, after 450ms of hover and at once on focus.

/** How long a pointer rests on a trigger before its tooltip opens (C-00 `Go…` tooltip). */
export const TOOLTIP_DELAY_MS = 450;

// ---- Menu --------------------------------------------------------------------------------------

export interface MenuItem {
  label: string;
  onSelect: () => void;
  /** Destructive actions read in brick. */
  danger?: boolean;
  disabled?: boolean;
  /** A short line under the label. */
  hint?: string;
  /** A registry icon before the label (14, ink-3). */
  icon?: IconName;
  /** Marks the current choice. A section in which any item sets this is a radio group: its items
   * are `menuitemradio`, the checked one carries a check and the weight 500. */
  checked?: boolean;
  /** The label opens a dialog, so it ends with "…" (U+2026). Asserted in development. */
  opensDialog?: boolean;
}

export interface MenuProps {
  trigger: ReactNode;
  /** Groups of items; each group is one white body on the tray. */
  sections: MenuItem[][];
  align?: "start" | "center" | "end";
  /** The menu's accessible name. */
  label?: string;
  /** Width in px: 220 by default (C-13), 176 for the view menu. */
  width?: number;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  /** The trigger does nothing: no pointer, no key opens the menu. */
  disabled?: boolean;
  /** Hold the menu open for a specimen. It is drawn in place under its trigger, not in a layer,
   * so a page of specimens stays a page; it takes no focus and nothing dismisses it. */
  forceState?: "open";
}

// Radix names a menu by its trigger (`aria-labelledby`), which would win over `aria-label`. A menu
// the caller names ("View") keeps that name, so the attribute is cleared.
const OWN_NAME = { "aria-labelledby": undefined } as unknown as object;

// A row: the registry icon, the label with an optional hint under it, then the check.
const ITEM =
  "relative flex min-h-[34px] cursor-default items-center gap-[8px] rounded-tile px-[10px] text-body outline-offset-[-2px] select-none data-[disabled]:text-ink-4 data-[highlighted]:bg-nav-fill data-[state=checked]:bg-nav-fill data-[state=checked]:font-medium";

function Row({ item }: { item: MenuItem }): JSX.Element {
  return (
    <>
      {item.icon !== undefined && <Icon name={item.icon} size={14} className="text-ink-3" />}
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate">{item.label}</span>
        {item.hint !== undefined && <span className="text-meta text-ink-3">{item.hint}</span>}
      </span>
    </>
  );
}

function rowClasses(item: MenuItem): string {
  return cn(ITEM, item.danger === true ? "text-red-ink" : "text-ink");
}

function rowProps(item: MenuItem): { "aria-haspopup"?: "dialog" } {
  if (item.opensDialog !== true) return {};
  assertDialogLabel(item.label, "MenuItem");
  return { "aria-haspopup": "dialog" };
}

const TRAY =
  "flex max-w-[calc(100vw-16px)] flex-col gap-[4px] rounded-menu bg-nested p-[4px] shadow-menu outline-none";
const SECTION =
  "flex max-h-[245px] flex-col gap-[1px] overflow-y-auto rounded-menu-inner bg-card p-[4px]";

const ALIGN = {
  start: "left-0",
  center: "left-1/2 -translate-x-1/2",
  end: "right-0",
} as const;

// The held menu: the same tray, rows and classes, drawn in place with the roles a real one has.
function StaticMenu({
  trigger,
  sections,
  align,
  label,
  width,
}: Required<Pick<MenuProps, "sections" | "align" | "width">> &
  Pick<MenuProps, "trigger"> & { label: string | undefined }): JSX.Element {
  return (
    <span className="relative inline-flex">
      <Slot aria-haspopup="menu" aria-expanded={true} data-state="open">
        {trigger}
      </Slot>
      <div
        role="menu"
        aria-label={label}
        style={{ width }}
        className={cn(TRAY, "absolute top-[calc(100%+4px)] z-10", ALIGN[align])}
      >
        {sections.map((items, n) => {
          const radio = items.some((item) => item.checked !== undefined);
          return (
            <div key={n} role="group" className={SECTION}>
              {items.map((item) => (
                <div
                  key={item.label}
                  role={radio ? "menuitemradio" : "menuitem"}
                  {...(radio ? { "aria-checked": item.checked === true } : {})}
                  {...(item.disabled === true
                    ? { "aria-disabled": true, "data-disabled": "" }
                    : {})}
                  {...(radio
                    ? { "data-state": item.checked === true ? "checked" : "unchecked" }
                    : {})}
                  tabIndex={-1}
                  className={rowClasses(item)}
                  {...rowProps(item)}
                >
                  <Row item={item} />
                  {radio && item.checked === true && (
                    <Icon name="check" size={12} strokeWidth={2} />
                  )}
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </span>
  );
}

/** A menu: a nested tray with white sections. Escape closes it and returns focus to the trigger;
 * ↓ on the trigger opens it and focuses the first item; ↑ ↓ Home End move. */
export function Menu({
  trigger,
  sections,
  align = "end",
  label,
  width = 220,
  open,
  onOpenChange,
  disabled = false,
  forceState,
}: MenuProps): JSX.Element {
  const animate = useMotion();
  // A menu is a layer of the OverlayStack: Escape closes it before the dialog or drawer it is in,
  // and it sits above every layer that is open, so it is never under the dialog that holds it.
  const [inner, setInner] = useState(false);
  const isOpen = open ?? inner;
  const set = (next: boolean): void => {
    setInner(next);
    onOpenChange?.(next);
  };
  const layer = useOverlayLayer({
    kind: "popover",
    modal: false,
    open: isOpen && forceState === undefined,
    onOpenChange: set,
  });
  if (forceState === "open") {
    return (
      <StaticMenu
        trigger={trigger}
        sections={sections}
        align={align}
        label={label}
        width={width}
      />
    );
  }
  return (
    <DropdownPrimitive.Root open={isOpen} onOpenChange={layer.onRootOpenChange}>
      <DropdownPrimitive.Trigger asChild disabled={disabled}>
        {trigger}
      </DropdownPrimitive.Trigger>
      <DropdownPrimitive.Portal>
        <DropdownPrimitive.Content
          align={align}
          sideOffset={4}
          collisionPadding={8}
          aria-label={label}
          {...(label === undefined ? {} : OWN_NAME)}
          style={{ width, zIndex: layer.panelZ }}
          className={cn(TRAY, animate && "motion-reveal")}
          onEscapeKeyDown={layer.onEscape}
        >
          {sections.map((items, n) => {
            const radio = items.some((item) => item.checked !== undefined);
            return (
              <DropdownPrimitive.Group key={n} className={SECTION}>
                {radio ? (
                  <DropdownPrimitive.RadioGroup
                    value={String(items.findIndex((item) => item.checked === true))}
                    className="flex flex-col gap-[1px]"
                  >
                    {items.map((item, i) => (
                      <DropdownPrimitive.RadioItem
                        key={item.label}
                        value={String(i)}
                        disabled={item.disabled === true}
                        onSelect={item.onSelect}
                        className={rowClasses(item)}
                        {...rowProps(item)}
                      >
                        <Row item={item} />
                        <DropdownPrimitive.ItemIndicator className="flex">
                          <Icon name="check" size={12} strokeWidth={2} />
                        </DropdownPrimitive.ItemIndicator>
                      </DropdownPrimitive.RadioItem>
                    ))}
                  </DropdownPrimitive.RadioGroup>
                ) : (
                  items.map((item) => (
                    <DropdownPrimitive.Item
                      key={item.label}
                      disabled={item.disabled === true}
                      onSelect={item.onSelect}
                      className={rowClasses(item)}
                      {...rowProps(item)}
                    >
                      <Row item={item} />
                    </DropdownPrimitive.Item>
                  ))
                )}
              </DropdownPrimitive.Group>
            );
          })}
        </DropdownPrimitive.Content>
      </DropdownPrimitive.Portal>
    </DropdownPrimitive.Root>
  );
}

// ---- Tooltip -----------------------------------------------------------------------------------

// A Tooltip outside a provider gets its own, so a specimen or a test needs no setup; the app
// mounts one TooltipProvider at the root so the delay is shared and skipped between neighbours.
const InProvider = createContext(false);

/** Mount once near the root (shared hover delay). */
export function TooltipProvider({ children }: { children: ReactNode }): JSX.Element {
  return (
    <TooltipPrimitive.Provider delayDuration={TOOLTIP_DELAY_MS} skipDelayDuration={200}>
      <InProvider.Provider value={true}>{children}</InProvider.Provider>
    </TooltipPrimitive.Provider>
  );
}

export interface TooltipProps {
  /** The first line, 12.5 ink. */
  content: ReactNode;
  /** A second line, 11.5 ink-3 ("Also: ..."). */
  detail?: ReactNode;
  children: ReactNode;
  side?: "top" | "right" | "bottom" | "left";
  /** Hold the tooltip open for a specimen, drawn in place beside its trigger. */
  forceState?: "open";
}

const TIP =
  "flex max-w-[280px] flex-col gap-[3px] rounded-nested bg-card px-[10px] py-[7px] shadow-pop";

const TIP_SIDE = {
  bottom: "top-[calc(100%+6px)] left-1/2 -translate-x-1/2",
  top: "bottom-[calc(100%+6px)] left-1/2 -translate-x-1/2",
  right: "left-[calc(100%+6px)] top-1/2 -translate-y-1/2",
  left: "right-[calc(100%+6px)] top-1/2 -translate-y-1/2",
} as const;

/** A short explanation on hover and focus; never the only place information lives. It names the
 * trigger by `aria-describedby` and is `role="tooltip"`. Radix opens it at once on keyboard
 * focus, and closes it on Escape. */
export function Tooltip({
  content,
  detail,
  children,
  side = "bottom",
  forceState,
}: TooltipProps): JSX.Element {
  const inProvider = useContext(InProvider);
  const id = useId();
  if (forceState === "open") {
    return (
      <span className="relative inline-flex">
        <Slot aria-describedby={id}>{children}</Slot>
        <span role="tooltip" id={id} className={cn(TIP, "absolute z-10 w-max", TIP_SIDE[side])}>
          <span className="text-dense text-ink">{content}</span>
          {detail !== undefined && <span className="text-meta text-ink-3">{detail}</span>}
        </span>
      </span>
    );
  }
  const root = (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side={side}
          sideOffset={6}
          collisionPadding={8}
          className={cn(TIP, "z-[70]")}
        >
          <span className="text-dense text-ink">{content}</span>
          {detail !== undefined && <span className="text-meta text-ink-3">{detail}</span>}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
  return inProvider ? (
    root
  ) : (
    <TooltipPrimitive.Provider delayDuration={TOOLTIP_DELAY_MS}>{root}</TooltipPrimitive.Provider>
  );
}
