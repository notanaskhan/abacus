import type { JSX, ReactNode } from "react";
import { AgentText } from "../agent-text";
import { cn } from "../cn";
import { Icon } from "../icons";
import { SectionBand } from "../workpaper/bands";

// MappingTable (L2; A-03-T12; the AUD-31 handoff, `kits/AUD31 Mapping`): the trial balance mapping
// sheet in the DataTable evidence grammar. Columns: Entity (multi-entity only) · Acct (mono) ·
// Account · Balance · Mapped to — grouping › FS line · Method · Confidence · actions. A dark
// SectionBand "NEEDS REVIEW · n" leads the 52-high rows that need a person (an agent reason, when
// there is one, is a second line of AgentText); a sel-bg sub-band "MAPPED · n" carries the host's
// "Group by FS line" control, then one collapsible group per grouping with its 30-high rows and the
// server's subtotal row. Every figure arrives formatted from the host: the kit sums nothing.
// Suggested mappings read ink-2 with the host's marker (C-31) until a person adopts them; rule
// matches carry no marker. A row is a button that selects (the host lights its source row).

export interface MappingTableRow {
  /** The account code: the row's identity. */
  id: string;
  entity?: string;
  code: string;
  name: string;
  /** The balance as formatted (credits in parentheses). */
  balance: string;
  balanceTone?: "pos" | "neg" | "zero" | "blank";
  /** "Grouping › FS line", or null while unmapped. */
  mapped: string | null;
  /** A suggestion not yet adopted: the mapping reads ink-2. */
  suggested?: boolean;
  /** The C-31 marker or "Edited by CD · was …" after the mapping. */
  marker?: ReactNode;
  method: string | null;
  confidence: string | null;
  confidenceTone?: "amber";
  /** The agent's one-line reason (review rows only); rendered through AgentText. */
  reason?: string;
  /** Accept · Change ⌄ (the host's controls; never on the agent's text). */
  actions?: ReactNode;
}

export interface MappingTableGroup {
  key: string;
  label: string;
  rows: readonly MappingTableRow[];
  open: boolean;
  /** The server's subtotal line ("Mapped 8,090,000 · interim TB line 8,400,000" + pill). */
  subtotal?: ReactNode;
}

export interface MappingTableProps {
  /** The table's accessible name. */
  label: string;
  /** Show the Entity column (a group of entities). */
  entities?: boolean;
  review?: { label: string; rows: readonly MappingTableRow[] };
  mapped: { label: string; control?: ReactNode; groups: readonly MappingTableGroup[] };
  selected?: string | null;
  onSelect?: (row: MappingTableRow) => void;
  onToggle?: (key: string) => void;
  /** An empty table's line (no accounts yet). */
  empty?: ReactNode;
  className?: string;
}

export const MAPPING_COLUMNS = {
  entity: "Entity",
  code: "Acct",
  account: "Account",
  balance: "Balance",
  mapped: "Mapped to — grouping › FS line",
  method: "Method",
  confidence: "Confidence",
} as const;

const TONE: Readonly<Record<NonNullable<MappingTableRow["balanceTone"]>, string>> = {
  pos: "text-ink",
  neg: "text-red",
  zero: "text-ink-4",
  blank: "text-ink-4",
};

function Row({
  row,
  entities,
  tall,
  selected,
  onSelect,
}: {
  row: MappingTableRow;
  entities: boolean;
  tall: boolean;
  selected: boolean;
  onSelect?: (row: MappingTableRow) => void;
}): JSX.Element {
  return (
    <tr
      data-mapping-row={row.id}
      {...(selected ? { "aria-selected": true } : {})}
      onClick={() => onSelect?.(row)}
      className={cn(
        "cursor-default align-top text-cell hairline-b",
        tall ? "h-[52px]" : "h-[30px]",
        selected ? "bg-sel-bg" : "hover:bg-nav-fill",
      )}
    >
      {entities && <td className="py-[7px] pl-[14px] text-ink-2">{row.entity ?? ""}</td>}
      <td className={cn("py-[7px] font-mono text-th", entities ? "pl-[8px]" : "pl-[14px]")}>
        <button
          type="button"
          className="text-left focus-visible:outline-offset-2"
          onClick={(e) => {
            e.stopPropagation();
            onSelect?.(row);
          }}
        >
          {row.code}
        </button>
      </td>
      <td className="py-[7px] pl-[8px]">
        <span className="block">{row.name}</span>
        {row.reason !== undefined && (
          <AgentText
            inline
            text={row.reason}
            className="block max-w-[420px] truncate text-meta text-ink-2"
          />
        )}
      </td>
      <td
        className={cn(
          "py-[7px] pr-[12px] text-right whitespace-nowrap tabular-nums",
          TONE[row.balanceTone ?? "pos"],
        )}
      >
        {row.balance}
      </td>
      <td className="py-[7px] pl-[8px]">
        <span className="flex flex-wrap items-center gap-[6px]">
          <span className={row.suggested === true ? "text-ink-2" : "text-ink"}>
            {row.mapped ?? "—"}
          </span>
          {row.marker}
        </span>
      </td>
      <td className="py-[7px] pl-[8px] text-ink-2">{row.method ?? ""}</td>
      <td
        className={cn(
          "py-[7px] pl-[8px]",
          row.confidenceTone === "amber" ? "text-amber-ink" : "text-ink-2",
        )}
      >
        {row.confidence ?? "—"}
      </td>
      <td className="py-[7px] pr-[14px] pl-[8px] text-right whitespace-nowrap">{row.actions}</td>
    </tr>
  );
}

export function MappingTable({
  label,
  entities = false,
  review,
  mapped,
  selected = null,
  onSelect,
  onToggle,
  empty,
  className,
}: MappingTableProps): JSX.Element {
  const span = entities ? 8 : 7;
  return (
    <table
      aria-label={label}
      data-mapping-table=""
      className={cn("w-full border-collapse text-cell", className)}
    >
      <thead>
        <tr className="h-[28px] bg-band-hd text-th text-ink-2 hairline-b">
          {entities && (
            <th className="pl-[14px] text-left font-normal">{MAPPING_COLUMNS.entity}</th>
          )}
          <th className={cn("text-left font-normal", entities ? "pl-[8px]" : "pl-[14px]")}>
            {MAPPING_COLUMNS.code}
          </th>
          <th className="pl-[8px] text-left font-normal">{MAPPING_COLUMNS.account}</th>
          <th className="pr-[12px] text-right font-normal">{MAPPING_COLUMNS.balance}</th>
          <th className="pl-[8px] text-left font-normal">{MAPPING_COLUMNS.mapped}</th>
          <th className="pl-[8px] text-left font-normal">{MAPPING_COLUMNS.method}</th>
          <th className="pl-[8px] text-left font-normal">{MAPPING_COLUMNS.confidence}</th>
          <th aria-hidden />
        </tr>
      </thead>
      {review !== undefined && review.rows.length > 0 && (
        <tbody data-mapping="review">
          <tr>
            <td colSpan={span} className="p-0">
              <SectionBand label={review.label} collapsible={false} />
            </td>
          </tr>
          {review.rows.map((r) => (
            <Row
              key={r.id}
              row={r}
              entities={entities}
              tall
              selected={r.id === selected}
              {...(onSelect === undefined ? {} : { onSelect })}
            />
          ))}
        </tbody>
      )}
      <tbody data-mapping="mapped">
        <tr className="h-[40px] bg-sel-bg">
          <td colSpan={span} className="px-[14px]">
            <span className="flex items-center justify-between gap-[8px]">
              <span className="text-band-dark text-ink uppercase">{mapped.label}</span>
              {mapped.control}
            </span>
          </td>
        </tr>
        {mapped.groups.length === 0 && empty !== undefined && (
          <tr>
            <td colSpan={span} className="px-[14px] py-[16px] text-meta text-ink-3">
              {empty}
            </td>
          </tr>
        )}
        {mapped.groups.flatMap((g) => [
          <tr key={`${g.key}:head`} data-mapping-group={g.key} className="h-[44px] hairline-b">
            <td colSpan={span} className="p-0">
              <button
                type="button"
                aria-expanded={g.open}
                onClick={() => onToggle?.(g.key)}
                className="flex h-[44px] w-full items-center gap-[10px] px-[14px] text-left text-body text-ink-2 hover:bg-nav-fill"
              >
                <Icon
                  name="chevron-right"
                  size={12}
                  className={cn("text-ink-3 transition-transform", g.open && "rotate-90")}
                />
                {g.label}
              </button>
            </td>
          </tr>,
          ...(g.open
            ? g.rows.map((r) => (
                <Row
                  key={`${g.key}:${r.id}`}
                  row={r}
                  entities={entities}
                  tall={false}
                  selected={r.id === selected}
                  {...(onSelect === undefined ? {} : { onSelect })}
                />
              ))
            : []),
          ...(g.open && g.subtotal !== undefined
            ? [
                <tr key={`${g.key}:subtotal`} data-mapping-subtotal={g.key} className="hairline-b">
                  <td colSpan={span} className="px-[14px] py-[8px] text-cell font-medium">
                    {g.subtotal}
                  </td>
                </tr>,
              ]
            : []),
        ])}
      </tbody>
    </table>
  );
}
