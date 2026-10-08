import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { JSX, ReactNode } from "react";

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
        <DialogPrimitive.Overlay className="fixed inset-0 bg-ink/40" />
        <DialogPrimitive.Content className="fixed top-1/2 left-1/2 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-[var(--radius-panel)] border border-line bg-surface p-6 shadow-lg">
          <DialogPrimitive.Title className="font-display text-xl font-semibold">
            {title}
          </DialogPrimitive.Title>
          {description === undefined ? (
            <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
          ) : (
            <DialogPrimitive.Description className="text-sm text-muted">
              {description}
            </DialogPrimitive.Description>
          )}
          <div className="mt-4">{children}</div>
          <DialogPrimitive.Close
            aria-label="Close"
            className="absolute top-4 right-4 rounded p-2 hover:bg-sunken"
          >
            <X aria-hidden="true" className="size-4" />
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
