import * as DropdownPrimitive from "@radix-ui/react-dropdown-menu";
import * as PopoverPrimitive from "@radix-ui/react-popover";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import type { JSX, ReactNode } from "react";
import { cn } from "../cn";

// Anchored overlays (TASK-101, the plan's O1): a popover card, a menu tray and a tooltip. Radix
// for behaviour (focus, keyboard, collision); the look from the tokens.

export function Popover({
  trigger,
  children,
  align = "end",
  width = 360,
  open,
  onOpenChange,
  label,
}: {
  trigger: ReactNode;
  children: ReactNode;
  align?: "start" | "center" | "end";
  width?: number;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  /** The popover's accessible name. */
  label?: string;
}): JSX.Element {
  return (
    <PopoverPrimitive.Root
      {...(open !== undefined ? { open } : {})}
      {...(onOpenChange !== undefined ? { onOpenChange } : {})}
    >
      <PopoverPrimitive.Trigger asChild>{trigger}</PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align={align}
          sideOffset={8}
          aria-label={label}
          style={{ width }}
          className="z-50 max-w-[calc(100vw-24px)] rounded-pane bg-card p-3.5 text-[13px] shadow-pop outline-none animate-[pop-in_180ms_var(--ease-out)]"
        >
          {children}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}

export interface MenuItem {
  label: string;
  onSelect: () => void;
  /** Destructive actions read in brick. */
  danger?: boolean;
  disabled?: boolean;
  /** A short line under the label. */
  hint?: string;
}

/** A menu tray: greige tray, white sections. `sections` are groups of items. */
export function Menu({
  trigger,
  sections,
  align = "end",
  label,
}: {
  trigger: ReactNode;
  sections: MenuItem[][];
  align?: "start" | "center" | "end";
  label?: string;
}): JSX.Element {
  return (
    <DropdownPrimitive.Root>
      <DropdownPrimitive.Trigger asChild>{trigger}</DropdownPrimitive.Trigger>
      <DropdownPrimitive.Portal>
        <DropdownPrimitive.Content
          align={align}
          sideOffset={8}
          aria-label={label}
          className="z-50 flex min-w-[220px] flex-col gap-1.5 rounded-[15px] bg-nested p-1.5 shadow-menu outline-none animate-[pop-in_180ms_var(--ease-out)]"
        >
          {sections.map((items, n) => (
            <DropdownPrimitive.Group key={n} className="rounded-[11px] bg-card p-1 shadow-e1">
              {items.map((item) => (
                <DropdownPrimitive.Item
                  key={item.label}
                  disabled={item.disabled === true}
                  onSelect={item.onSelect}
                  className={cn(
                    "flex cursor-default flex-col rounded-[8px] px-2.5 py-1.5 text-[13px] outline-none select-none data-[disabled]:opacity-45 data-[highlighted]:bg-nav-fill",
                    item.danger === true ? "text-red-ink" : "text-ink",
                  )}
                >
                  {item.label}
                  {item.hint !== undefined && (
                    <span className="text-[11.5px] text-ink-3">{item.hint}</span>
                  )}
                </DropdownPrimitive.Item>
              ))}
            </DropdownPrimitive.Group>
          ))}
        </DropdownPrimitive.Content>
      </DropdownPrimitive.Portal>
    </DropdownPrimitive.Root>
  );
}

/** Mount once near the root (shared hover delay). */
export function TooltipProvider({ children }: { children: ReactNode }): JSX.Element {
  return (
    <TooltipPrimitive.Provider delayDuration={350} skipDelayDuration={200}>
      {children}
    </TooltipPrimitive.Provider>
  );
}

/** A short explanation on hover and focus; never the only place information lives. */
export function Tooltip({
  content,
  children,
}: {
  content: ReactNode;
  children: ReactNode;
}): JSX.Element {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          sideOffset={6}
          className="z-[70] max-w-[280px] rounded-[8px] bg-espresso px-2.5 py-1.5 text-[12px] leading-[1.4] text-on-dark shadow-e3"
        >
          {content}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}
