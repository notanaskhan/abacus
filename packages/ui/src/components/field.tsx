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
        "h-9 w-full rounded-md border border-neutral-300 bg-white px-3 text-sm focus-visible:outline-2 focus-visible:outline-neutral-900",
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
  return <LabelPrimitive.Root className={cn("text-sm font-medium", className)} {...props} />;
}
