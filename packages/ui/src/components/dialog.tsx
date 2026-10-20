import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { JSX, ReactNode } from "react";

// Dialog (TASK-091): 560 wide on the shell ground, radius 14, a white header with the title
// centred and a round close, over a light espresso scrim.
export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  trigger,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  trigger?: ReactNode;
  children: ReactNode;
}): JSX.Element {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      {trigger !== undefined && (
        <DialogPrimitive.Trigger asChild>{trigger}</DialogPrimitive.Trigger>
      )}
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 bg-espresso/22" />
        <DialogPrimitive.Content className="fixed top-1/2 left-1/2 flex max-h-[calc(100vh-4rem)] w-[calc(100%-2rem)] max-w-[560px] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-dialog bg-shell shadow-modal">
          <div className="relative flex h-[52px] shrink-0 items-center justify-center border-b-[0.5px] border-hair bg-card px-12">
            <DialogPrimitive.Title className="truncate text-[14.5px] font-medium tracking-[-0.012em]">
              {title}
            </DialogPrimitive.Title>
            <DialogPrimitive.Close
              aria-label="Close"
              className="absolute top-1/2 right-3 flex size-[30px] -translate-y-1/2 items-center justify-center rounded-[7px] bg-nav-fill text-ink-2 hover:bg-sel-bg hover:text-ink"
            >
              <X aria-hidden="true" className="size-3.5" />
            </DialogPrimitive.Close>
          </div>
          <div className="overflow-y-auto px-4 pt-3 pb-4">
            {description === undefined ? (
              <DialogPrimitive.Description className="sr-only">
                {title}
              </DialogPrimitive.Description>
            ) : (
              <DialogPrimitive.Description className="mb-3 text-[12.5px] leading-[1.5] text-ink-2">
                {description}
              </DialogPrimitive.Description>
            )}
            {children}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
