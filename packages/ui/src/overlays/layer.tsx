import * as DialogPrimitive from "@radix-ui/react-dialog";
import { type JSX, type ReactNode, useRef } from "react";
import { cn } from "../cn";
import { useMotion } from "../motion";
import { DiscardGuard } from "./confirm";
import { FrameMode, type InitialFocus, Scrim, type ScrimLevel, focusInitial } from "./frame";
import type { OverlayKind } from "./stack";
import { useOverlayLayer } from "./stack-react";

// One modal layer: a Radix dialog that joins the OverlayStack. Dialog, SheetModal, FullSheet,
// Drawer, the command palette and the wizard are this with different panels. It gives them focus
// trapped and returned to the opener, Escape and outside presses for the topmost layer only, the
// scrim, the dirty guard, scroll lock (Radix, with the CSS rule in base.css for the CSP) and the
// enter and exit motion, which is dropped under reduced motion.

export interface LayerProps {
  kind: OverlayKind;
  /** False for a peek: no scrim, no trap, no page lock, and the page behind stays live. */
  modal?: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  dirty?: boolean;
  /** The layer's name, for "What you typed in {title} will be lost." */
  title: string;
  scrim?: ScrimLevel;
  /** The scrim holds the panel and centres it (a dialog); otherwise the panel positions itself. */
  centred?: boolean;
  /** How the scrim lays the panel out when `centred`: centred by default, from the top for the
   * command palette. */
  scrimClassName?: string;
  /** The panel's classes: its box and, unless centred, its place. */
  className: string;
  /** The panel's enter and exit motion classes, dropped under reduced motion. */
  motion: string;
  initialFocus: InitialFocus;
  role?: "dialog" | "alertdialog" | "complementary";
  /** The panel has no description element (the palette): say so, so Radix does not warn. */
  noDescription?: boolean;
  /** A Radix trigger for the layer, so a press on it opens the layer and focus returns to it. */
  trigger?: ReactNode;
  children: ReactNode;
}

export function Layer({
  kind,
  modal = true,
  open,
  onOpenChange,
  dirty,
  title,
  scrim = "dialog",
  centred = false,
  scrimClassName = "grid place-items-center p-[24px]",
  className,
  motion,
  initialFocus,
  role,
  noDescription = false,
  trigger,
  children,
}: LayerProps): JSX.Element {
  const animate = useMotion();
  const layer = useOverlayLayer({ kind, modal, open, dirty: dirty ?? false, onOpenChange });
  const ref = useRef<HTMLDivElement>(null);
  const peek = !modal;

  const panel = (
    <DialogPrimitive.Content
      ref={ref}
      data-overlay={kind}
      {...(role === undefined ? {} : { role })}
      {...(noDescription ? { "aria-describedby": undefined } : {})}
      style={centred ? undefined : { zIndex: layer.panelZ }}
      className={cn(className, animate && motion)}
      onEscapeKeyDown={layer.onEscape}
      onPointerDownOutside={
        peek
          ? (event) => {
              event.preventDefault();
            }
          : layer.onlyTop
      }
      {...(peek
        ? {
            onInteractOutside: (event: { preventDefault: () => void }) => {
              event.preventDefault();
            },
          }
        : {})}
      onOpenAutoFocus={(event) => {
        // A peek takes no focus: the page stays where the person is working.
        if (peek) event.preventDefault();
        else focusInitial(event, ref.current, initialFocus);
      }}
      onCloseAutoFocus={(event) => {
        layer.returnFocus(event, peek);
      }}
    >
      <FrameMode live>{children}</FrameMode>
    </DialogPrimitive.Content>
  );

  return (
    <>
      <DialogPrimitive.Root open={open} modal={modal} onOpenChange={layer.onRootOpenChange}>
        {trigger !== undefined && (
          <DialogPrimitive.Trigger asChild>{trigger}</DialogPrimitive.Trigger>
        )}
        <DialogPrimitive.Portal>
          {modal ? (
            centred ? (
              <Scrim level={scrim} z={layer.scrimZ} animate={animate} className={scrimClassName}>
                {panel}
              </Scrim>
            ) : (
              <>
                <Scrim level={scrim} z={layer.scrimZ} animate={animate} />
                {panel}
              </>
            )
          ) : (
            panel
          )}
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>
      {layer.guarding && (
        <DiscardGuard title={title} onKeepEditing={layer.keepEditing} onDiscard={layer.discard} />
      )}
    </>
  );
}
