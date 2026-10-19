import { Slot } from "@radix-ui/react-slot";
import { type VariantProps, cva } from "class-variance-authority";
import type { ButtonHTMLAttributes, JSX } from "react";
import { cn } from "../cn";

// Buttons (TASK-091; squared corners, TASK-093): one dark primary per surface, white secondary on a 0.5px ring, tonal
// and ghost for quiet actions; press scales to .985.
const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-1.5 rounded-[7px] whitespace-nowrap select-none transition-[background-color,box-shadow,transform] duration-150 active:scale-[.985] disabled:pointer-events-none disabled:opacity-45 [&_svg]:size-3.5",
  {
    variants: {
      variant: {
        default: "bg-espresso font-medium text-on-dark shadow-cta hover:bg-cta-hover",
        outline: "bg-card text-ink shadow-e1 hover:bg-nav-fill",
        tonal: "bg-chip text-ink hover:bg-tonal-hover",
        ghost: "text-ink-2 hover:bg-nav-fill hover:text-ink",
        danger: "bg-red-tint font-medium text-red-ink hover:bg-red-tint-hover",
        success: "bg-green font-medium text-on-dark shadow-cta hover:bg-green-hover",
      },
      size: {
        default: "h-[30px] px-3.5 text-[13px]",
        sm: "h-[26px] px-3 text-[12.5px]",
        lg: "h-[34px] px-4 text-[13.5px]",
        icon: "size-7 p-0",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export function Button({
  className,
  variant,
  size,
  asChild = false,
  type = "button",
  ...props
}: ButtonProps): JSX.Element {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      className={cn(buttonVariants({ variant, size }), className)}
      {...(asChild ? {} : { type })}
      {...props}
    />
  );
}
