import * as DialogPrimitive from "@radix-ui/react-dialog";
import { type JSX, type ReactNode, createContext, useContext } from "react";
import { cn } from "../cn";
import { IconButton } from "../components/button";

// What every layer's panel is made of (C-22 Modal, C-23 Drawer): the scrim, the title, the round
// close, the description. A panel is drawn twice: live, inside a Radix dialog, where the title and
// the close are Radix's so the dialog is named and closes; and held in place for a specimen
// (`forceState="open"`), where they are a plain heading and button and nothing is a layer.

/** A props type that also takes `undefined` for each optional prop, so a caller can pass its own
 * optional prop straight on (exactOptionalPropertyTypes). */
export type Loose<T> = { [K in keyof T]: T[K] | undefined };

const LiveContext = createContext(true);

/** Wrap a panel's content: `live` false draws a heading and a button instead of Radix's. */
export function FrameMode({
  live,
  children,
}: {
  live: boolean;
  children: ReactNode;
}): JSX.Element {
  return <LiveContext.Provider value={live}>{children}</LiveContext.Provider>;
}

export function FrameTitle({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}): JSX.Element {
  const live = useContext(LiveContext);
  return live ? (
    <DialogPrimitive.Title className={className}>{children}</DialogPrimitive.Title>
  ) : (
    <h2 className={className}>{children}</h2>
  );
}

export function FrameDescription({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}): JSX.Element {
  const live = useContext(LiveContext);
  return live ? (
    <DialogPrimitive.Description className={className}>{children}</DialogPrimitive.Description>
  ) : (
    <p className={className}>{children}</p>
  );
}

/** The 30 round close on nav-fill, X 14 (C-22, C-23). It is the first thing a modal drawer
 * focuses, so it carries `data-overlay-close`. */
export function FrameClose({
  onClose,
  className,
}: {
  /** Only for a specimen; a live close is Radix's and calls `onOpenChange(false)`. */
  onClose?: () => void;
  className?: string;
}): JSX.Element {
  const live = useContext(LiveContext);
  const button = (
    <IconButton
      icon="x"
      label="Close"
      variant="fill"
      data-overlay-close=""
      className={cn("text-ink-2", className)}
      {...(live || onClose === undefined ? {} : { onClick: onClose })}
    />
  );
  return live ? <DialogPrimitive.Close asChild>{button}</DialogPrimitive.Close> : button;
}

/** A description that is not shown: assistive technology reads it, the page does not. */
export function HiddenDescription({ text }: { text: string }): JSX.Element {
  return <FrameDescription className="sr-only">{text}</FrameDescription>;
}

// ---- Scrim -------------------------------------------------------------------------------------

/** .22 for dialogs and drawers, .28 for agent sheets (O3), .30 for full sheets (O4, O6). */
export type ScrimLevel = "dialog" | "agent" | "sheet";

const LEVEL: Record<ScrimLevel, string> = {
  dialog: "bg-(--scrim)",
  agent: "bg-(--scrim-agent)",
  sheet: "bg-(--scrim-sheet)",
};

/** The scrim: a fixed fill with a 0.5px blur at saturate .9 that fades in over 180ms. A press on
 * it is an outside press: Radix reports it, the layer decides (a dirty form asks first). It can
 * hold the panel, which a dialog needs to be centred in it. */
export function Scrim({
  level,
  z,
  animate,
  className,
  children,
}: {
  level: ScrimLevel;
  z: string;
  animate: boolean;
  className?: string;
  children?: ReactNode;
}): JSX.Element {
  return (
    <DialogPrimitive.Overlay
      data-scrim={level}
      style={{ zIndex: z }}
      className={cn(
        "fixed inset-0 backdrop-blur-[0.5px] backdrop-saturate-[0.9]",
        LEVEL[level],
        animate && "motion-fade data-[state=closed]:motion-fade-out",
        className,
      )}
    >
      {children}
    </DialogPrimitive.Overlay>
  );
}

// ---- Initial focus -----------------------------------------------------------------------------

export type InitialFocus = "field" | "close" | "none";

const FIELD =
  'input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"]):not([type="file"]):not([disabled]):not([readonly]), textarea:not([disabled]):not([readonly]), select:not([disabled])';
const CHECKBOX =
  'input[type="checkbox"]:not([disabled]), [role="checkbox"]:not([aria-disabled="true"])';
const ACTION = "[data-overlay-action] :is(button, a[href]):not([disabled])";
const CLOSE = "[data-overlay-close]";

/**
 * Where focus lands when a layer opens (C-22): the first field, else the first checkbox, else the
 * primary action; a modal drawer and a full sheet start on the close button. Call it from
 * `onOpenAutoFocus`: it stops Radix's own choice, which is the first tabbable thing in the panel.
 */
export function focusInitial(
  event: { preventDefault: () => void },
  root: HTMLElement | null,
  mode: InitialFocus,
): void {
  event.preventDefault();
  if (root === null || mode === "none") return;
  const target =
    mode === "field"
      ? (root.querySelector<HTMLElement>(FIELD) ??
        root.querySelector<HTMLElement>(CHECKBOX) ??
        root.querySelector<HTMLElement>(ACTION))
      : null;
  (target ?? root.querySelector<HTMLElement>(CLOSE) ?? root).focus({ preventScroll: true });
}
