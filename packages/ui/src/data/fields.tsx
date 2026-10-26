import { type JSX, useState, useSyncExternalStore } from "react";
import { cn } from "../cn";
import { Amount } from "../components/amount";
import { Button } from "../components/button";
import type { ForceState } from "../force-state";
import { type AmountStyle } from "../format";
import { Icon } from "../icons";
import { Popover } from "../overlays/popover";
import { useMatch, useMatchStore } from "../tracing/match";
import type { MatchId } from "../tracing/types";

// Field rows (C-01 spec 05, `kind: 'field'`; F-05-T52): the values read from a W-2 or 1099, or a
// worksheet's lines, next to the document viewer. A row is min 42, padding 6 12, 13px: the label,
// then a 96 value box (up to 140) in tabular figures. A row whose match is the scope's active one
// (or that is `matched`) draws the value box in the match fill with its 1px line over 360ms and
// its label at 500; hovering the row lights its match on the page (E1). A mismatch draws the value
// in red ink with the Flag on. Flag and Info are 28 round ghost buttons, shown on hover, while
// flagged or while Info is open: Flag toggles and calls `onFlag`; Info opens the sticky source
// note. Values are the server's decimal strings; nothing here computes (ADR-050).

export interface FieldItem {
  id: string;
  /** "Line 3b · Ordinary dividends", "Box 1 · Wages, tips, other compensation". */
  label: string;
  /** A decimal string, or null for blank. */
  value: string | null;
  /** Default `cents` (31,846.20); a worksheet line is `whole`. */
  format?: AmountStyle;
  /** Lights with its region on the document (a typed C4 locator's id, INV-2). */
  match?: MatchId;
  /** Matched to the open document. */
  matched?: boolean;
  /** The value disagrees with the document: red ink, Flag on. */
  mismatch?: boolean;
  /** Initially flagged. */
  flagged?: boolean;
  /** Where the value came from: "Northwind Robotics W-2 2025.pdf · page 1 · box 1". */
  source?: string;
  /** The agent's proposed value, not yet accepted: the value in a dashed match box, with a
   * person's Accept and Reject under it (TPL-09a; the ghost value is one of the three purples). */
  proposed?: boolean;
}

export interface FieldBlockProps {
  /** The 32 block header: "W-2 · Northwind Robotics, Inc.", "Wages". */
  title: string;
  /** The header's right meta: "2025". */
  meta?: string;
  rows: readonly FieldItem[];
  /** The value box, 96 to 140 wide. */
  valueWidth?: number;
  selected?: string | null;
  onSelect?: (row: FieldItem) => void;
  onFlag?: (row: FieldItem, flagged: boolean) => void;
  /** A proposed value's Accept (it opens the approve modal) and Reject. */
  onAccept?: (row: FieldItem) => void;
  onReject?: (row: FieldItem) => void;
  /** Hold one row in a state for a specimen. */
  forceState?: { row: string; state: Extract<ForceState, "hover" | "open"> };
  className?: string;
}

const GHOST =
  "inline-flex size-[28px] flex-none items-center justify-center rounded-pill text-ink-3 transition-[background-color,opacity] duration-[180ms] hover:bg-nav-fill";

/** A block of field rows under its 32 header. */
export function FieldBlock({
  title,
  meta,
  rows,
  valueWidth = 96,
  selected,
  onSelect,
  onFlag,
  onAccept,
  onReject,
  forceState,
  className,
}: FieldBlockProps): JSX.Element {
  return (
    <section data-fields="" aria-label={title} className={cn("flex flex-col", className)}>
      <header className="flex h-[32px] items-center gap-[8px] px-[12px]">
        <h3 className="min-w-0 flex-1 truncate text-body font-medium">{title}</h3>
        {meta !== undefined && <span className="text-meta text-ink-3">{meta}</span>}
      </header>
      <ul className="flex flex-col">
        {rows.map((row) => (
          <FieldRow
            key={row.id}
            row={row}
            valueWidth={valueWidth}
            selected={selected === row.id}
            {...(onSelect === undefined ? {} : { onSelect })}
            {...(onFlag === undefined ? {} : { onFlag })}
            {...(onAccept === undefined ? {} : { onAccept })}
            {...(onReject === undefined ? {} : { onReject })}
            {...(forceState?.row === row.id ? { forceState: forceState.state } : {})}
          />
        ))}
      </ul>
    </section>
  );
}

export interface FieldRowProps {
  row: FieldItem;
  valueWidth?: number;
  selected?: boolean;
  onSelect?: (row: FieldItem) => void;
  onFlag?: (row: FieldItem, flagged: boolean) => void;
  onAccept?: (row: FieldItem) => void;
  onReject?: (row: FieldItem) => void;
  forceState?: Extract<ForceState, "hover" | "open">;
}

const NO_MATCH = "" as MatchId;

export function FieldRow({
  row,
  valueWidth = 96,
  selected = false,
  onSelect,
  onFlag,
  onAccept,
  onReject,
  forceState,
}: FieldRowProps): JSX.Element {
  const store = useMatchStore();
  const { bind } = useMatch(row.match ?? NO_MATCH, "row");
  const live = useSyncExternalStore(
    store.subscribe,
    () => row.match !== undefined && store.get().id === row.match,
    () => false,
  );
  const [flag, setFlag] = useState(row.flagged === true || row.mismatch === true);
  const [info, setInfo] = useState(false);
  const lit = live || row.matched === true;
  const shown = flag || info || forceState !== undefined;
  const events = row.match === undefined ? {} : bind;
  return (
    <li
      {...events}
      data-field={row.id}
      data-matched={lit ? "" : undefined}
      data-mismatch={row.mismatch === true ? "" : undefined}
      {...(forceState === "hover" ? { "data-force": "hover" } : {})}
      onClick={() => onSelect?.(row)}
      className={cn(
        "group flex min-h-[42px] items-center gap-[8px] px-[12px] py-[6px] text-body hairline-t",
        "hover:bg-nested data-[force=hover]:bg-nested",
        selected && "bg-sel-bg hover:bg-sel-bg",
      )}
    >
      <span
        className={cn(
          "min-w-0 flex-1 [font-variant-numeric:normal]",
          (lit || selected) && "font-medium",
        )}
      >
        {row.label}
      </span>
      {row.proposed === true ? (
        <span
          data-field-proposed=""
          style={{ width: valueWidth }}
          className="flex flex-none flex-col items-end gap-[6px]"
        >
          <span
            data-field-value=""
            aria-label={`Proposed value for ${row.label}`}
            className="w-full rounded-value border border-dashed border-match-line bg-match-bg px-[6px] py-[2px] text-right whitespace-nowrap text-match-ink tabular-nums"
          >
            {row.value === null ? "" : <Amount value={row.value} style={row.format ?? "cents"} />}
          </span>
          <span className="flex gap-[6px]">
            <Button
              variant="primary"
              size="xs"
              onClick={(event) => {
                event.stopPropagation();
                onAccept?.(row);
              }}
            >
              Accept
            </Button>
            <Button
              variant="secondary"
              size="xs"
              onClick={(event) => {
                event.stopPropagation();
                onReject?.(row);
              }}
            >
              Reject
            </Button>
          </span>
        </span>
      ) : (
        <span
          data-field-value=""
          style={{ width: valueWidth }}
          className={cn(
            "-my-[3px] flex-none rounded-value px-[6px] py-[3px] text-right whitespace-nowrap tabular-nums",
            "transition-[background-color,box-shadow] duration-[360ms]",
            lit && "bg-match-bg ring-1 ring-match-line",
            row.mismatch === true && "text-red-ink",
          )}
        >
          {row.value === null ? "" : <Amount value={row.value} style={row.format ?? "cents"} />}
        </span>
      )}
      <span
        className={cn(
          "flex flex-none items-center gap-[2px] opacity-0 transition-opacity duration-[180ms]",
          "group-hover:opacity-100 group-focus-within:opacity-100",
          shown && "opacity-100",
        )}
      >
        <button
          type="button"
          aria-label={`Flag ${row.label}`}
          aria-pressed={flag}
          className={cn(GHOST, flag && "text-red")}
          onClick={(event) => {
            event.stopPropagation();
            setFlag(!flag);
            onFlag?.(row, !flag);
          }}
        >
          <Icon name="flag" size={12} />
        </button>
        {row.source !== undefined && (
          <Popover
            label={`Source of ${row.label}`}
            width={280}
            open={info || forceState === "open"}
            onOpenChange={setInfo}
            {...(forceState === "open" ? { forceState: "open" as const } : {})}
            trigger={
              <button
                type="button"
                aria-label={`Info for ${row.label}`}
                className={GHOST}
                onClick={(event) => {
                  event.stopPropagation();
                }}
              >
                <Icon name="info" size={12} />
              </button>
            }
          >
            <p className="text-body font-medium">{row.label}</p>
            <p className="mt-[4px] text-meta text-ink-2">{row.source}</p>
          </Popover>
        )}
      </span>
    </li>
  );
}
