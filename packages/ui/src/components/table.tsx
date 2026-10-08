import type { HTMLAttributes, JSX, TdHTMLAttributes, ThHTMLAttributes } from "react";
import { cn } from "../cn";

export function Table({ className, ...props }: HTMLAttributes<HTMLTableElement>): JSX.Element {
  return (
    <table
      className={cn("w-full border-collapse text-left text-sm tabular-nums", className)}
      {...props}
    />
  );
}

export function Th({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>): JSX.Element {
  return (
    <th
      scope="col"
      className={cn(
        "border-b border-line bg-sunken px-3 py-2 text-xs font-semibold tracking-wide text-muted",
        className,
      )}
      {...props}
    />
  );
}

export function Td({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>): JSX.Element {
  return <td className={cn("border-b border-line px-3 py-2.5 align-top", className)} {...props} />;
}
