import { type JSX, type ReactNode, useId, useState } from "react";
import { cn } from "../cn";
import { Pill } from "../components/pill";
import { type ForceState, forceAttr } from "../force-state";
import { Icon } from "../icons";
import type { SourceDoc, SourceDocSize, SourceDocStatus } from "./types";

// SourceDocGroup and SourceDocRow (C-15 File kit; F-05-T50): the source documents a record has
// asked for, grouped by category, on the T2 canvas (TPL-02 "Source Documents") and in the C-15
// list. A group band says "{received} of {total}" in words and collapses; a row is one button that
// opens the document in the viewer through `onOpen` (the screen switches the dock to Viewer). The
// status is words: "Received" on the green pill with a check, "Uploaded – needs review" on amber,
// or "Requested" in ink-3 beside an empty ring. Never colour alone, never a red for a missing file.
//
//   cockpit  TPL-02: band 31 on band-hd, 13.5 / 500; rows 52, a 15 file glyph, 13.5 title, 12 path
//   compact  C-15:   band 32 on nested, 12.5 / 500 with a folder; rows 40, padding 6 12 6 34

export const SOURCE_DOC_WORD: Record<SourceDocStatus, string> = {
  received: "Received",
  review: "Uploaded – needs review",
  requested: "Requested",
};

const BAND: Record<SourceDocSize, string> = {
  cockpit: "h-[31px] bg-band-hd px-[12px] text-section hairline-b",
  compact: "h-[32px] bg-nested px-[12px] text-dense font-medium",
};

export interface SourceDocGroupProps {
  /** The category: "Plan documents". */
  title: string;
  /** Counts from the data: "3 of 5". */
  received: number;
  total: number;
  size?: SourceDocSize;
  /** Controlled; uncontrolled from `defaultOpen` (true). */
  open?: boolean;
  defaultOpen?: boolean;
  onToggle?: (open: boolean) => void;
  forceState?: Extract<ForceState, "hover" | "focus">;
  /** `SourceDocRow`s. */
  children?: ReactNode;
}

/** A category of requested documents: a collapsing band over its rows. */
export function SourceDocGroup({
  title,
  received,
  total,
  size = "cockpit",
  open,
  defaultOpen = true,
  onToggle,
  forceState,
  children,
}: SourceDocGroupProps): JSX.Element {
  const listId = useId();
  const [own, setOwn] = useState(defaultOpen);
  const shown = open ?? own;
  const count = `${String(received)} of ${String(total)}`;
  return (
    <section data-source-docs="group" aria-label={title} className="flex flex-col">
      <button
        type="button"
        aria-expanded={shown}
        aria-controls={listId}
        {...forceAttr(forceState)}
        onClick={() => {
          setOwn(!shown);
          onToggle?.(!shown);
        }}
        className={cn(
          "flex w-full flex-none items-center gap-[8px] text-left focus-visible:outline-offset-[-2px]",
          "hover:bg-nav-fill data-[force=hover]:bg-nav-fill",
          BAND[size],
        )}
      >
        {size === "compact" && <Icon name="folder" size={14} className="flex-none text-ink-2" />}
        <span className="min-w-0 truncate">{title}</span>
        {size === "compact" && <span className="font-normal text-ink-3">{count}</span>}
        <span className="flex-1" />
        {size === "cockpit" && (
          <span className="flex-none text-dense font-normal text-ink-3">{count}</span>
        )}
        <Icon
          name="chevron-down"
          size={12}
          className={cn(
            "flex-none text-ink-3 transition-transform duration-[180ms] ease-out",
            !shown && "-rotate-90",
          )}
        />
      </button>
      <ul id={listId} hidden={!shown} className="flex flex-col">
        {children}
      </ul>
    </section>
  );
}

export interface SourceDocRowProps {
  doc: SourceDoc;
  size?: SourceDocSize;
  /** The document open in the viewer. */
  selected?: boolean;
  /** Cockpit rows at the audit cockpit's geometry (AUD-02: min 44, padding 8 12 9) rather than
   * TPL-02's and AUD-03's 52. */
  tight?: boolean;
  /** Opens the document in the viewer (SHL-08). */
  onOpen?: (doc: SourceDoc) => void;
  forceState?: Extract<ForceState, "hover" | "focus">;
}

/** One requested document: its title and file path, and where it stands. */
export function SourceDocRow({
  doc,
  size = "cockpit",
  selected = false,
  tight = false,
  onOpen,
  forceState,
}: SourceDocRowProps): JSX.Element {
  const cockpit = size === "cockpit";
  return (
    <li className="flex">
      <button
        type="button"
        data-source-docs="row"
        data-status={doc.status}
        {...(selected ? { "aria-current": "true" as const } : {})}
        {...forceAttr(forceState)}
        onClick={() => onOpen?.(doc)}
        className={cn(
          "flex w-full items-center gap-[10px] text-left hairline-b focus-visible:outline-offset-[-2px]",
          "hover:bg-nav-fill data-[force=hover]:bg-nav-fill",
          selected && "bg-sel-bg hover:bg-sel-bg",
          cockpit
            ? tight
              ? "min-h-[44px] px-[12px] pt-[8px] pb-[9px]"
              : "min-h-[52px] px-[14px] py-[8px]"
            : "min-h-[40px] py-[6px] pr-[12px] pl-[34px]",
        )}
      >
        {cockpit && <Icon name="file" size={15} className="flex-none text-ink-3" />}
        <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
          <span
            className={cn("truncate text-ink", cockpit ? "text-nav leading-[1.3]" : "text-dense")}
          >
            {doc.title}
          </span>
          {doc.path !== undefined && (
            <span
              data-source-docs="path"
              className={cn(
                "truncate text-ink-3",
                cockpit ? "text-cell" : "text-pill-sm font-normal",
              )}
            >
              {doc.path}
            </span>
          )}
        </span>
        <SourceDocStatusMark status={doc.status} size={size} />
      </button>
    </li>
  );
}

/** The row's status in words. */
export function SourceDocStatusMark({
  status,
  size = "cockpit",
}: {
  status: SourceDocStatus;
  size?: SourceDocSize;
}): JSX.Element {
  if (status === "requested") {
    return (
      <span
        data-source-docs="status"
        className={cn(
          "inline-flex flex-none items-center gap-[6px] text-ink-3",
          size === "cockpit" ? "text-dense" : "text-meta",
        )}
      >
        {SOURCE_DOC_WORD.requested}
        <span
          aria-hidden="true"
          className={cn(
            "flex-none rounded-pill inset-ring-[1.3px] inset-ring-ink-4",
            size === "cockpit" ? "size-[15px]" : "size-[14px]",
          )}
        />
      </span>
    );
  }
  return (
    <Pill
      data-source-docs="status"
      variant={status === "received" ? "green" : "amber"}
      size="card-state"
      check={status === "received"}
      className="flex-none flex-row-reverse"
    >
      {SOURCE_DOC_WORD[status]}
    </Pill>
  );
}
