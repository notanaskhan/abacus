import type { HTMLAttributes, JSX, TdHTMLAttributes, ThHTMLAttributes } from "react";
import { cn } from "../cn";

// Table styles (TASK-091): a 30px band header in ink-2, 0.5px hair rules, tabular figures; the
// full DataTable grammars come later.
export function Table({ className, ...props }: HTMLAttributes<HTMLTableElement>): JSX.Element {
  return (
    <table
      className={cn("w-full border-collapse text-left text-[12.5px] tabular-nums", className)}
      {...props}
    />
  );
}

export function Th({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>): JSX.Element {
  return (
    <th
      scope="col"
      className={cn(
        "h-[30px] border-b-[0.5px] border-hair bg-band-hd px-3 text-[11.5px] font-normal whitespace-nowrap text-ink-2",
        className,
      )}
      {...props}
    />
  );
}

export function Td({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>): JSX.Element {
  return (
    <td
      className={cn("border-b-[0.5px] border-hair px-3 py-2 align-middle", className)}
      {...props}
    />
  );
}
