import type { JSX, ReactNode } from "react";
import { cn } from "../cn";
import {
  FrameClose,
  FrameDescription,
  FrameMode,
  FrameTitle,
  HiddenDescription,
  type ScrimLevel,
} from "./frame";
import { Layer } from "./layer";

// Dialog (C-22 Modal, O-grammar "dialog sizes"): sm 420, md 560, lg 760, xl 1140. Radius 14 on the
// shell ground with the modal shadow, entering with opacity and a scale from .98. The header is 52
// high and white: the close on the left, a short centred title, and the one primary action on the
// right; there is no footer (a ConfirmDialog has one). The primary waits until the form can be
// sent (give the Button `disabled`), and a destructive one is a `destructive` Button, never a red
// fill. Body content goes in white cards on the shell, never straight on it.
//
// A dirty dialog does not close on Escape, the close or the scrim: it asks "Discard changes?".
// Focus starts on the first field, else the first checkbox, else the primary action.

export type DialogSize = "sm" | "md" | "lg" | "xl";

export const DIALOG_WIDTH: Record<DialogSize, number> = { sm: 420, md: 560, lg: 760, xl: 1140 };

const WIDTH: Record<DialogSize, string> = {
  sm: "w-[420px]",
  md: "w-[560px]",
  lg: "w-[760px]",
  xl: "w-[1140px]",
};

const BOX =
  "relative flex max-h-[calc(100vh-120px)] max-w-full flex-col overflow-hidden rounded-dialog bg-shell shadow-modal";

export interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** Shown above the body; without it the title is read as the description. */
  description?: string;
  /** A control that opens the dialog; focus returns to it on close. */
  trigger?: ReactNode;
  size?: DialogSize;
  /** The one primary action, drawn in the header's right. Disable it until the form can be sent. */
  action?: ReactNode;
  /** Unsaved changes: closing asks "Discard changes?" first. */
  dirty?: boolean;
  /** .22 for a dialog; .28 when an agent's sheet opens it. */
  scrim?: Extract<ScrimLevel, "dialog" | "agent">;
  children: ReactNode;
  /** Hold the dialog open in place for a specimen: no layer, no scrim, no trap. */
  forceState?: "open";
}

function Frame({
  title,
  description,
  action,
  children,
  onClose,
}: {
  title: string;
  description: string | undefined;
  action: ReactNode;
  children: ReactNode;
  onClose?: () => void;
}): JSX.Element {
  return (
    <>
      <header className="relative flex h-[52px] shrink-0 items-center justify-between border-b-[0.5px] border-hair bg-card px-[12px]">
        <FrameClose {...(onClose === undefined ? {} : { onClose })} />
        <FrameTitle className="absolute top-1/2 left-1/2 max-w-[60%] -translate-x-1/2 -translate-y-1/2 truncate text-pane font-medium tracking-[-0.012em]">
          {title}
        </FrameTitle>
        {action === undefined ? (
          <span aria-hidden="true" className="size-[30px]" />
        ) : (
          <span data-overlay-action="" className="contents">
            {action}
          </span>
        )}
      </header>
      <div className="flex min-h-0 flex-1 flex-col gap-[10px] overflow-y-auto p-[12px]">
        {description === undefined ? (
          <HiddenDescription text={title} />
        ) : (
          <FrameDescription className="text-para text-ink-2">{description}</FrameDescription>
        )}
        {children}
      </div>
    </>
  );
}

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  trigger,
  size = "md",
  action,
  dirty,
  scrim = "dialog",
  children,
  forceState,
}: DialogProps): JSX.Element {
  if (forceState === "open") {
    return (
      <div role="group" aria-label={title} className={cn(BOX, WIDTH[size])}>
        <FrameMode live={false}>
          <Frame title={title} description={description} action={action} onClose={() => undefined}>
            {children}
          </Frame>
        </FrameMode>
      </div>
    );
  }
  return (
    <Layer
      kind="dialog"
      open={open}
      onOpenChange={onOpenChange}
      dirty={dirty ?? false}
      title={title}
      scrim={scrim}
      centred
      className={cn(BOX, WIDTH[size])}
      motion="motion-scale-in data-[state=closed]:motion-fade-out"
      initialFocus="field"
      trigger={trigger}
    >
      <Frame title={title} description={description} action={action}>
        {children}
      </Frame>
    </Layer>
  );
}
