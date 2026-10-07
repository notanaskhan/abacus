import type { HTMLAttributes, JSX, TdHTMLAttributes, ThHTMLAttributes } from "react";
import { cn } from "../cn";

export function Table({ className, ...props }: HTMLAttributes<HTMLTableElement>): JSX.Element {
  return (
    <table className={cn("w-full border-collapse text-left text-sm", className)} {...props} />
  );
}

export function Th({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>): JSX.Element {
  return (
    <th
      scope="col"
      className={cn(
        "border-b border-neutral-200 px-3 py-2 font-medium text-neutral-600",
        className,
      )}
      {...props}
    />
  );
}

export function Td({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>): JSX.Element {
  return (
    <td className={cn("border-b border-neutral-100 px-3 py-2 align-top", className)} {...props} />
  );
}
