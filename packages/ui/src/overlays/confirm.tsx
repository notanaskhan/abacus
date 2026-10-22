import * as DialogPrimitive from "@radix-ui/react-dialog";
import { type JSX, type ReactNode, useRef } from "react";
import { cn } from "../cn";
import { Button } from "../components/button";
import { useMotion } from "../motion";
import { FrameDescription, FrameMode, FrameTitle, Scrim } from "./frame";
import { useOverlayLayer } from "./stack-react";

// ConfirmDialog (C-22): no header, the title and the text in the body, then Cancel and the confirm
// in a footer. It is an alertdialog, 420 wide, and a destructive confirm is white with brick text,
// never a red fill. "Discard changes?" is this same dialog, opened by a dirty layer over itself.

const BOX =
  "relative flex max-h-[calc(100vh-120px)] w-[420px] max-w-full flex-col overflow-hidden rounded-dialog bg-shell shadow-modal";

export interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** The text under the title. */
  children?: ReactNode;
  /** The confirm button's words ("Delete"). */
  confirmLabel: string;
  cancelLabel?: string;
  /** Brick text on white (the default). False for a confirm that is not destructive. */
  destructive?: boolean;
  /** The user confirmed. The dialog closes itself afterwards. */
  onConfirm: () => void;
  /** Which button takes focus first: Cancel, so a stray Enter cannot confirm. */
  initialFocus?: "cancel" | "confirm";
  /** Hold the dialog open in place for a specimen: no layer, no scrim, no trap. */
  forceState?: "open";
}

function Body({
  title,
  text,
  confirmLabel,
  cancelLabel,
  destructive,
  initialFocus,
  onCancel,
  onConfirm,
}: {
  title: string;
  text: ReactNode;
  confirmLabel: string;
  cancelLabel: string;
  destructive: boolean;
  initialFocus: "cancel" | "confirm";
  onCancel?: () => void;
  onConfirm: () => void;
}): JSX.Element {
  return (
    <>
      <div className="px-[16px] pt-[16px] pb-[4px]">
        <FrameTitle className="block text-pane font-medium tracking-[-0.012em]">
          {title}
        </FrameTitle>
        {text !== undefined && text !== null && (
          <FrameDescription className="mt-[6px] text-body leading-[1.5]">{text}</FrameDescription>
        )}
      </div>
      <div className="flex shrink-0 justify-end gap-[8px] p-[12px]">
        {onCancel === undefined ? (
          <DialogPrimitive.Close asChild>
            <Button
              variant="secondary"
              data-overlay-initial={initialFocus === "cancel" ? "" : undefined}
            >
              {cancelLabel}
            </Button>
          </DialogPrimitive.Close>
        ) : (
          <Button variant="secondary" onClick={onCancel}>
            {cancelLabel}
          </Button>
        )}
        <Button
          variant={destructive ? "destructive" : "primary"}
          data-overlay-initial={initialFocus === "confirm" ? "" : undefined}
          onClick={onConfirm}
        >
          {confirmLabel}
        </Button>
      </div>
    </>
  );
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  children,
  confirmLabel,
  cancelLabel = "Cancel",
  destructive = true,
  onConfirm,
  initialFocus = "cancel",
  forceState,
}: ConfirmDialogProps): JSX.Element {
  const animate = useMotion();
  const layer = useOverlayLayer({
    kind: "confirm",
    modal: true,
    open: open && forceState === undefined,
    onOpenChange,
  });
  const ref = useRef<HTMLDivElement>(null);
  const confirm = (): void => {
    onConfirm();
    onOpenChange(false);
  };

  if (forceState === "open") {
    return (
      <div role="group" aria-label={title} className={BOX}>
        <FrameMode live={false}>
          <Body
            title={title}
            text={children}
            confirmLabel={confirmLabel}
            cancelLabel={cancelLabel}
            destructive={destructive}
            initialFocus={initialFocus}
            onCancel={() => undefined}
            onConfirm={() => undefined}
          />
        </FrameMode>
      </div>
    );
  }

  return (
    <DialogPrimitive.Root open={open} onOpenChange={layer.onRootOpenChange}>
      <DialogPrimitive.Portal>
        <Scrim
          level="dialog"
          z={layer.scrimZ}
          animate={animate}
          className="grid place-items-center p-[24px]"
        >
          <DialogPrimitive.Content
            ref={ref}
            role="alertdialog"
            data-overlay="confirm"
            {...(children === undefined ? { "aria-describedby": undefined } : {})}
            className={cn(BOX, animate && "motion-scale-in data-[state=closed]:motion-fade-out")}
            onEscapeKeyDown={layer.onEscape}
            onPointerDownOutside={layer.onlyTop}
            onOpenAutoFocus={(event) => {
              event.preventDefault();
              ref.current?.querySelector<HTMLElement>("[data-overlay-initial]")?.focus();
            }}
            onCloseAutoFocus={layer.returnFocus}
          >
            <Body
              title={title}
              text={children}
              confirmLabel={confirmLabel}
              cancelLabel={cancelLabel}
              destructive={destructive}
              initialFocus={initialFocus}
              onConfirm={confirm}
            />
          </DialogPrimitive.Content>
        </Scrim>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/** The "Discard changes?" guard a dirty layer opens over itself (C-22). */
export function DiscardGuard({
  title,
  onKeepEditing,
  onDiscard,
}: {
  /** The layer's title: "What you typed in {title} will be lost." */
  title: string;
  onKeepEditing: () => void;
  onDiscard: () => void;
}): JSX.Element {
  return (
    <ConfirmDialog
      open
      title="Discard changes?"
      confirmLabel="Discard"
      cancelLabel="Keep editing"
      initialFocus="cancel"
      onOpenChange={(next) => {
        if (!next) onKeepEditing();
      }}
      onConfirm={onDiscard}
    >
      {`What you typed in ${title} will be lost.`}
    </ConfirmDialog>
  );
}
