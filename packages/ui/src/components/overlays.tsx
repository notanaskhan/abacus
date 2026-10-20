import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { JSX, ReactNode } from "react";
import { cn } from "../cn";

// Overlays (TASK-101, the plan's O2 drawer and O3 sheet). Both are Radix dialogs: focus is
// trapped, Escape closes, the opener gets focus back.

interface OverlayProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** For assistive technology when there's no visible description. */
  description?: string;
  /** Right of the title (a status pill, record stepping). */
  meta?: ReactNode;
  /** A pinned footer (the primary action). */
  footer?: ReactNode;
  children: ReactNode;
}

function Close(): JSX.Element {
  return (
    <DialogPrimitive.Close
      aria-label="Close"
      className="flex size-[30px] shrink-0 items-center justify-center rounded-[7px] bg-nav-fill text-ink-2 hover:bg-sel-bg hover:text-ink"
    >
      <X aria-hidden="true" className="size-3.5" />
    </DialogPrimitive.Close>
  );
}

function Description({ title, text }: { title: string; text: string | undefined }): JSX.Element {
  return text === undefined ? (
    <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
  ) : (
    <DialogPrimitive.Description className="mb-3 text-[12.5px] leading-[1.5] text-ink-2">
      {text}
    </DialogPrimitive.Description>
  );
}

/** A right drawer (O2): a record's detail beside the list it came from. 10px from the edges,
 * radius 14, on the shell ground with a white 46px header. Width 420–480. */
export function Drawer({
  open,
  onOpenChange,
  title,
  description,
  meta,
  footer,
  width = 480,
  children,
}: OverlayProps & { width?: 420 | 480 | 560 }): JSX.Element {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-[rgba(43,31,23,.12)]" />
        <DialogPrimitive.Content
          className={cn(
            "fixed top-2.5 right-2.5 bottom-2.5 z-50 flex max-w-[calc(100vw-20px)] flex-col overflow-hidden rounded-dialog bg-shell shadow-modal",
            "data-[state=open]:animate-[drawer-in_260ms_var(--ease-out)]",
            width === 420 ? "w-[420px]" : width === 560 ? "w-[560px]" : "w-[480px]",
          )}
        >
          <div className="flex h-[46px] shrink-0 items-center gap-2 border-b-[0.5px] border-hair bg-card pr-2 pl-4">
            <DialogPrimitive.Title className="min-w-0 flex-1 truncate text-[14.5px] font-medium tracking-[-0.012em]">
              {title}
            </DialogPrimitive.Title>
            {meta}
            <Close />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-3.5">
            <Description title={title} text={description} />
            {children}
          </div>
          {footer !== undefined && (
            <div className="flex shrink-0 items-center justify-end gap-2 border-t-[0.5px] border-hair bg-card px-3.5 py-2.5">
              {footer}
            </div>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/** A sheet (O3): a focused task over the page (draft a follow-up, approve, sign). 500 wide,
 * rising from the bottom with rounded top corners, a 56px header with the title centred, the
 * action on the right. */
export function Sheet({
  open,
  onOpenChange,
  title,
  description,
  meta,
  footer,
  children,
}: OverlayProps): JSX.Element {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-[rgba(43,31,23,.28)]" />
        <DialogPrimitive.Content className="fixed top-[52px] bottom-0 left-1/2 z-50 flex w-[calc(100%-2rem)] max-w-[500px] -translate-x-1/2 flex-col overflow-hidden rounded-t-[16px] bg-shell shadow-modal data-[state=open]:animate-[sheet-in_260ms_var(--ease-out)]">
          <div className="relative flex h-[56px] shrink-0 items-center justify-center border-b-[0.5px] border-hair bg-card px-14">
            <span className="absolute top-1/2 left-3 -translate-y-1/2">
              <Close />
            </span>
            <DialogPrimitive.Title className="truncate text-[15px] font-medium tracking-[-0.012em]">
              {title}
            </DialogPrimitive.Title>
            {meta !== undefined && (
              <span className="absolute top-1/2 right-3 -translate-y-1/2">{meta}</span>
            )}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-3.5">
            <Description title={title} text={description} />
            {children}
          </div>
          {footer !== undefined && (
            <div className="flex shrink-0 items-center justify-end gap-2 border-t-[0.5px] border-hair bg-card px-3.5 py-2.5">
              {footer}
            </div>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/** A fieldset card inside a drawer or sheet (r10, e1). */
export function Fieldset({
  title,
  className,
  children,
}: {
  title?: string;
  className?: string;
  children: ReactNode;
}): JSX.Element {
  return (
    <section className={cn("mb-2.5 rounded-nested bg-card p-3 shadow-e1", className)}>
      {title !== undefined && (
        <h3 className="mb-2 text-[12.5px] font-medium text-ink-2">{title}</h3>
      )}
      {children}
    </section>
  );
}
