import * as LabelPrimitive from "@radix-ui/react-label";
import type { ComponentProps, InputHTMLAttributes, JSX } from "react";
import { cn } from "../cn";

export function Input({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>): JSX.Element {
  return (
    <input
      className={cn(
        "h-9 w-full rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm text-ink placeholder:text-muted",
        className,
      )}
      {...props}
    />
  );
}

export function Label({
  className,
  ...props
}: ComponentProps<typeof LabelPrimitive.Root>): JSX.Element {
  return (
    <LabelPrimitive.Root className={cn("text-sm font-semibold text-ink", className)} {...props} />
  );
}
