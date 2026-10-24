import type { JSX } from "react";
import { cn } from "../cn";
import { DataGrid, type DataGridProps } from "./data-grid";
import type { TableColumn, TableRow } from "./types";

// The evidence grammar's frame (C-01 spec 03; F-05-T43): audit workpaper tables as block cards on
// a well. Each block is a white e1 card, radius 12, margin 12 12 0, with a 32px header (13 / 500,
// optional 11.5 meta on the right) over an `evidence` DataGrid. `card={false}` drops the cards and
// the well, so the tables sit flush in the pane. Totals are the server's rows. The leadsheet
// grammar (F-05-T52) uses the same frame: its block title is its only header (32, padding 0 14).

export interface EvidenceBlock {
  id: string;
  title?: string;
  meta?: string;
  columns: readonly TableColumn[];
  rows: readonly TableRow[];
}

export interface EvidenceTableProps extends Pick<
  DataGridProps,
  "onSelect" | "onOpen" | "onExplain" | "onIssue" | "cellMatch" | "rowMatch"
> {
  /** Default `evidence`. */
  grammar?: "evidence" | "leadsheet";
  /** The accessible name each block's grid starts with ("Trial Balance"). */
  label: string;
  blocks: readonly EvidenceBlock[];
  /** Default true: cards on a well. */
  card?: boolean;
  className?: string;
}

export function EvidenceTable({
  label,
  blocks,
  card = true,
  grammar = "evidence",
  className,
  ...handlers
}: EvidenceTableProps): JSX.Element {
  return (
    <div
      data-grammar={grammar}
      data-card={card ? "" : undefined}
      className={cn("flex flex-col", card && "bg-shell pb-[12px]", className)}
    >
      {blocks.map((block) => (
        <section
          key={block.id}
          aria-label={block.title ?? label}
          className={cn(
            "flex flex-col",
            card && "mx-[12px] mt-[12px] overflow-hidden rounded-pane bg-card shadow-e1",
          )}
        >
          {block.title !== undefined && (
            <header
              className={cn(
                "flex h-[32px] items-center gap-[8px]",
                grammar === "leadsheet" ? "px-[14px]" : "px-[12px]",
              )}
            >
              <h3 className="min-w-0 flex-1 truncate text-body font-medium">{block.title}</h3>
              {block.meta !== undefined && (
                <span className="text-meta text-ink-3">{block.meta}</span>
              )}
            </header>
          )}
          <DataGrid
            label={block.title === undefined ? label : `${label}: ${block.title}`}
            grammar={grammar}
            columns={block.columns}
            rows={block.rows}
            {...handlers}
          />
        </section>
      ))}
    </div>
  );
}
