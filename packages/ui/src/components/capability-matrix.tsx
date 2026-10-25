import { Lock } from "lucide-react";
import type { JSX } from "react";
import { cn } from "../cn";
import { Tooltip } from "./popover";

// CapabilityMatrix (G-01 §5.2; the component-kits digest's "PermissionMatrix"; ADM-02b): a
// read-only grid of capabilities by role template. Each cell is one of five marks, always with a
// text alternative: ● allowed (an 8px ink dot, with its condition under it when it has one:
// "QM owner", "EP only"), ◐ allowed with a condition (a half disc whose condition opens on hover
// and on focus), D "may draft or propose only", — no access (ink-4), and a lock for a cell no
// firm may change. The grid is a real table with scoped headers; the highlighted column (the
// selected template) sits on the selection fill. It decides nothing: the cells are the server's.

export type CapabilityCell = "allow" | "conditional" | "delegated" | "deny" | "locked";

export interface CapabilityColumn {
  key: string;
  label: string;
}

export interface CapabilityRow {
  key: string;
  label: string;
  cells: Readonly<Record<string, CapabilityCell>>;
  /** By column key: the condition text of a ◐, or the note under a ●. */
  conditions?: Readonly<Record<string, string>>;
}

export interface CapabilityWords {
  /** "Allowed" */
  allow: string;
  /** "Allowed: QM owner" */
  allowWith: (condition: string) => string;
  /** "Allowed with a condition: staff work only" */
  conditional: (condition: string) => string;
  /** "Draft or propose only" */
  delegated: string;
  /** "No access" */
  deny: string;
  /** "Locked" */
  locked: string;
}

export interface CapabilityMatrixProps {
  /** The table's accessible name. */
  label: string;
  /** The first header: "Capability". */
  header: string;
  columns: readonly CapabilityColumn[];
  rows: readonly CapabilityRow[];
  /** The column to highlight (the selected template). */
  highlight?: string | null;
  words: CapabilityWords;
  className?: string;
}

/** A cell's text alternative. */
export function capabilityText(
  cell: CapabilityCell,
  condition: string | undefined,
  words: CapabilityWords,
): string {
  switch (cell) {
    case "allow":
      return condition === undefined ? words.allow : words.allowWith(condition);
    case "conditional":
      return words.conditional(condition ?? "");
    case "delegated":
      return words.delegated;
    case "deny":
      return words.deny;
    case "locked":
      return words.locked;
  }
}

function HalfDisc(): JSX.Element {
  return (
    <svg aria-hidden="true" width={14} height={14} viewBox="0 0 14 14">
      <path d="M 7 0 A 7 7 0 0 0 7 14 Z" className="fill-ink" />
      <circle cx={7} cy={7} r={6.3} fill="none" className="stroke-ink" strokeWidth={1.4} />
    </svg>
  );
}

function Mark({
  cell,
  condition,
  words,
}: {
  cell: CapabilityCell;
  condition: string | undefined;
  words: CapabilityWords;
}): JSX.Element {
  const text = capabilityText(cell, condition, words);
  switch (cell) {
    case "allow":
      return (
        <span role="img" aria-label={text} className="flex flex-col items-center gap-[2px]">
          <span aria-hidden="true" className="size-[8px] rounded-full bg-ink" />
          {condition !== undefined && (
            <span aria-hidden="true" className="text-micro font-normal text-ink-3">
              {condition}
            </span>
          )}
        </span>
      );
    case "conditional":
      return (
        <Tooltip content={condition ?? ""}>
          <button
            type="button"
            aria-label={text}
            data-capability="conditional"
            className="inline-flex size-[22px] items-center justify-center rounded-pill hover:bg-nav-fill focus-visible:bg-nav-fill"
          >
            <HalfDisc />
          </button>
        </Tooltip>
      );
    case "delegated":
      return (
        <span role="img" aria-label={text} className="text-meta font-medium text-ink-3">
          <span aria-hidden="true">D</span>
        </span>
      );
    case "deny":
      return (
        <span role="img" aria-label={text} className="text-body text-ink-4">
          <span aria-hidden="true">—</span>
        </span>
      );
    case "locked":
      return (
        <span role="img" aria-label={text} className="inline-flex text-ink-4">
          <Lock aria-hidden="true" size={10} strokeWidth={1.8} />
        </span>
      );
  }
}

export function CapabilityMatrix({
  label,
  header,
  columns,
  rows,
  highlight = null,
  words,
  className,
}: CapabilityMatrixProps): JSX.Element {
  return (
    <table
      aria-label={label}
      data-capability-matrix=""
      className={cn("w-full border-collapse text-left text-body", className)}
    >
      <thead>
        <tr>
          <th
            scope="col"
            className="h-[30px] bg-band-hd px-[16px] text-th font-normal whitespace-nowrap text-ink-2 hairline-b"
          >
            {header}
          </th>
          {columns.map((c) => (
            <th
              key={c.key}
              scope="col"
              {...(c.key === highlight ? { "data-highlight": "" } : {})}
              className={cn(
                "h-[30px] px-[4px] text-center text-th font-normal whitespace-nowrap hairline-b",
                c.key === highlight ? "bg-sel-bg font-medium text-ink" : "bg-band-hd text-ink-2",
              )}
            >
              {c.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key} data-capability-row={row.key}>
            <th
              scope="row"
              className="min-h-[32px] px-[16px] py-[7px] text-body font-normal text-ink hairline-b"
            >
              {row.label}
            </th>
            {columns.map((c) => (
              <td
                key={c.key}
                className={cn(
                  "h-[32px] px-[4px] py-[4px] text-center align-middle hairline-b",
                  c.key === highlight && "bg-nav-fill",
                )}
              >
                <span className="inline-flex justify-center">
                  <Mark
                    cell={row.cells[c.key] ?? "deny"}
                    condition={row.conditions?.[c.key]}
                    words={words}
                  />
                </span>
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
