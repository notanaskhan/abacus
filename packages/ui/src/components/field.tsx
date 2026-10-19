import * as LabelPrimitive from "@radix-ui/react-label";
import type { ComponentProps, InputHTMLAttributes, JSX } from "react";
import { cn } from "../cn";

/** A recessed field: nested greige with an inset hair ring, white and ringed on focus. */
export function Input({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>): JSX.Element {
  return (
    <input
      className={cn(
        "h-[30px] w-full rounded-tile border-0 bg-nested px-2.5 text-[13px] text-ink inset-shadow-hair transition-colors placeholder:text-ink-3 hover:bg-sel-bg focus:bg-card",
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
    <LabelPrimitive.Root
      className={cn("text-[12px] font-medium text-ink-2", className)}
      {...props}
    />
  );
}
