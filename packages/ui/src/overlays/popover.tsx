import * as PopoverPrimitive from "@radix-ui/react-popover";
import { Slot } from "@radix-ui/react-slot";
import { type HTMLAttributes, type JSX, type ReactNode, useState } from "react";
import { cn } from "../cn";
import { useMotion } from "../motion";
import { useOverlayLayer } from "./stack-react";

// Popover (O1, plan 04 section 5.3): a card anchored 8px from its trigger, 266 to 462 wide, in two
// looks. `card` is a white radius-12 card on the pop shadow (Assign to, a form, a detail). `tray`
// is the nested #EFEEEB tray of radius 15 around white sections of radius 11 (the New… menu of a
// pane, the firm menu); put its sections in `PopoverSection`s. Radix is the behaviour: Escape
// closes it and returns focus to the trigger, a press outside closes it, it flips at an edge.
//
// It is non-modal (the page stays live, no scrim, no trap), but it is a layer of the
// OverlayStack: Escape reaches the topmost layer only, so a popover inside a dialog inside a drawer
// closes first, then the dialog, then the drawer. It enters in 180ms and not at all under reduced
// motion.

export type PopoverVariant = "card" | "tray";

const CARD = "rounded-pane bg-card p-[14px] text-body shadow-pop";
const TRAY = "flex flex-col gap-[4px] rounded-menu bg-nested p-[4px] shadow-menu";

export interface PopoverProps {
  trigger: ReactNode;
  children: ReactNode;
  align?: "start" | "center" | "end";
  /** Width in px, 266 to 462. */
  width?: number;
  variant?: PopoverVariant;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  /** The popover's accessible name. */
  label?: string;
  /** Hold the popover open in place under its trigger for a specimen. */
  forceState?: "open";
}

const ALIGN = {
  start: "left-0",
  center: "left-1/2 -translate-x-1/2",
  end: "right-0",
} as const;

export function Popover({
  trigger,
  children,
  align = "end",
  width = 360,
  variant = "card",
  open,
  onOpenChange,
  label,
  forceState,
}: PopoverProps): JSX.Element {
  const animate = useMotion();
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
  const look = variant === "tray" ? TRAY : CARD;

  if (forceState === "open") {
    return (
      <span className="relative inline-flex">
        <Slot aria-haspopup="dialog" aria-expanded={true} data-state="open">
          {trigger}
        </Slot>
        <div
          role="dialog"
          aria-label={label}
          style={{ width }}
          className={cn(look, "absolute top-[calc(100%+8px)] z-10", ALIGN[align])}
        >
          {children}
        </div>
      </span>
    );
  }

  return (
    <PopoverPrimitive.Root open={isOpen} onOpenChange={layer.onRootOpenChange}>
      <PopoverPrimitive.Trigger asChild>{trigger}</PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          data-overlay="popover"
          data-variant={variant}
          align={align}
          sideOffset={8}
          collisionPadding={8}
          aria-label={label}
          style={{ width, zIndex: layer.panelZ }}
          className={cn("max-w-[calc(100vw-16px)] outline-none", look, animate && "motion-pop")}
          onEscapeKeyDown={layer.onEscape}
          onPointerDownOutside={layer.onlyTop}
        >
          {children}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}

/** A white section of a `tray` popover: radius 11, padding 4. */
export function PopoverSection({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>): JSX.Element {
  return (
    <div
      className={cn("flex flex-col gap-[1px] rounded-menu-inner bg-card p-[4px]", className)}
      {...props}
    />
  );
}
