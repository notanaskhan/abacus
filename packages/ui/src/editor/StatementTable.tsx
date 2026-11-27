// F-08-T28 (DEC-6026): a read-only statement table as a React node view (C1). ProseMirror owns
// the node; React draws its rows; nothing is contenteditable inside it and nothing writes HTML.
import { NodeViewWrapper, type ReactNodeViewProps } from "@tiptap/react";
import type { JSX } from "react";
import { cn } from "../cn";
import { paperAmount } from "./format";
import type { StatementRow, StatementTableAttrs } from "./types";

const INDENT = ["pl-0", "pl-[12px]", "pl-[24px]"] as const;

function Row({ row, columns }: { row: StatementRow; columns: number }): JSX.Element {
  if (row.heading === true) {
    return (
      <tr data-statement-row={row.key}>
        <th
          scope="colgroup"
          colSpan={columns + 1}
          className="pt-[6px] text-left text-[9.5px] font-normal tracking-[.06em]"
        >
          {row.caption}
        </th>
      </tr>
    );
  }
  return (
    <tr data-statement-row={row.key}>
      <th scope="row" className={cn("text-left font-normal", INDENT[row.indent])}>
        {row.caption}
      </th>
      {row.amounts.map((value, i) => (
        <td
          key={`${row.key}:${String(i)}`}
          data-amount={value ?? ""}
          className={cn(
            "w-[74px] text-right tabular-nums",
            row.rule === "above" && "border-t-[0.5px] border-doc-ink",
            row.rule === "double_below" && "border-b-[3px] border-double border-doc-ink",
          )}
        >
          {paperAmount(value, row.dollar === true)}
        </td>
      ))}
    </tr>
  );
}

export function StatementTableView({ node }: ReactNodeViewProps): JSX.Element {
  const attrs = node.attrs as StatementTableAttrs;
  return (
    <NodeViewWrapper
      as="div"
      contentEditable={false}
      data-statement={attrs.key}
      data-readonly="true"
      className="my-[6px] select-text"
    >
      <table className="w-full border-collapse font-doc text-[9.5px] leading-[15px] text-doc-ink">
        <thead>
          <tr>
            <th scope="col" className="sr-only">
              Caption
            </th>
            {attrs.columns.map((c) => (
              <th
                key={c}
                scope="col"
                className="w-[74px] text-right font-normal underline decoration-[0.5px] underline-offset-2"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {attrs.rows.map((row) => (
            <Row key={row.key} row={row} columns={attrs.columns.length} />
          ))}
        </tbody>
      </table>
    </NodeViewWrapper>
  );
}
