import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { type JSX, type ReactNode, useState, useSyncExternalStore } from "react";
import { AgentText } from "../agent-text";
import { cn } from "../cn";
import { PRESS } from "../components/control-classes";
import { HIT } from "../components/hit-area";
import { type ForceState, forceAttr } from "../force-state";
import { Icon } from "../icons";
import { useMatchStore } from "./match";
import { AnchoredPopoverHost } from "./popover-host";
import type { CitationPayload, CitationView, MatchId } from "./types";

// The C-07 Cite kit's visuals (F-05-T41): the CiteMarker inline in prose, the CitationPopover the
// E2 host anchors beside the lit cell, and the CitationChip footer ("Citations (n)", "Procedures
// (n)") with its upward menu. Every agent-produced number reaches its source in one hover. Never a
// blue link or a footnote superscript, never a citation without its location, and purple only for
// tracing. What a citation lights comes from its typed locator (INV-2), never from text.

/** The match a citation lights, or none. */
export function citationMatch(cite: CitationView): MatchId | null {
  return cite.match;
}

// ---- CiteMarker ---------------------------------------------------------------------------------

/** Focus from the keyboard, not a click (a click pins instead). */
function keyboardFocus(el: Element): boolean {
  try {
    return el.matches(":focus-visible");
  } catch {
    return true;
  }
}

export interface CiteMarkerProps {
  cite: CitationView;
  /** The sources the popover steps through ("1 of 3"); default this one alone. */
  list?: readonly CitationView[];
  /** Hold the marker lit for a specimen. */
  forceState?: Extract<ForceState, "hover" | "focus" | "open">;
}

const MARKER = cn(
  "relative ml-[3px] inline-flex h-[17px] items-center rounded-pill px-[5px] align-[1px] text-micro tracking-normal tabular-nums",
  "bg-nested text-ink-2 inset-shadow-hair transition-[background-color,box-shadow,color] duration-[180ms]",
  "hover:bg-match-bg hover:text-match-ink hover:ring-1 hover:ring-match-line",
  "data-[lit]:bg-match-bg data-[lit]:text-match-ink data-[lit]:ring-1 data-[lit]:ring-match-line",
  "data-[force=hover]:bg-match-bg data-[force=hover]:text-match-ink data-[force=hover]:ring-1 data-[force=hover]:ring-match-line",
  "outline-offset-1",
  HIT.marker,
);

/** The inline citation number: hover or focus lights its match and opens the popover after 150ms;
 * a click pins it. */
export function CiteMarker({ cite, list, forceState }: CiteMarkerProps): JSX.Element {
  const store = useMatchStore();
  const sources = list ?? [cite];
  const index = Math.max(sources.indexOf(cite), 0);
  const id = citationMatch(cite);
  const open = useSyncExternalStore(
    store.subscribe,
    () => {
      const s = store.get();
      return s.payload !== null && s.payload.list[s.payload.index] === cite;
    },
    () => false,
  );
  const lit = open || forceState === "open";
  const payload = (): CitationPayload => ({ list: sources, index });
  return (
    <button
      type="button"
      data-cite-marker={cite.n}
      {...(lit ? { "data-lit": "" } : {})}
      {...forceAttr(forceState === "open" ? undefined : forceState)}
      aria-label={`Citation ${String(cite.n)}: ${cite.title}`}
      aria-expanded={lit}
      aria-haspopup="dialog"
      className={MARKER}
      onPointerEnter={(event) => {
        store.intent(id, event.currentTarget, "marker", payload());
      }}
      onPointerLeave={() => {
        store.release("marker");
      }}
      onFocus={(event) => {
        if (keyboardFocus(event.currentTarget)) {
          store.intent(id, event.currentTarget, "marker", payload());
        }
      }}
      onBlur={() => {
        store.release("marker");
      }}
      onClick={(event) => {
        store.togglePin(id, event.currentTarget, payload());
      }}
    >
      {cite.n}
    </button>
  );
}

// ---- CitationPopover ----------------------------------------------------------------------------

const GHOST =
  "inline-flex size-[22px] flex-none items-center justify-center rounded-pill text-ink-3 hover:bg-nav-fill hover:text-ink disabled:text-ink-4 disabled:hover:bg-transparent";

export interface CitationPopoverProps {
  payload: CitationPayload;
  /** ‹ ›: show another source of the same claim (the host re-lights its match). */
  onStep?: (index: number) => void;
  /** The open button: the CitationDialog (P-03, SHL-07). Without it the button is not drawn. */
  onOpenDialog?: (cite: CitationView) => void;
}

/** The 372 card: the source's title, its quote, and its location with the stepper. */
export function CitationPopover({
  payload,
  onStep,
  onOpenDialog,
}: CitationPopoverProps): JSX.Element | null {
  const cite = payload.list[payload.index];
  if (cite === undefined) return null;
  const many = payload.list.length > 1;
  return (
    <div data-cite="popover" className="flex flex-col">
      <p className="px-[15px] pt-[13px] pb-[12px] text-section leading-[1.3] font-medium tracking-[-0.012em] hairline-b">
        {cite.title}
      </p>
      <div className="flex gap-[10px] px-[15px] pt-[12px] pb-[10px]">
        <Icon name="file" size={13} className="mt-[2px] flex-none text-ink-3" />
        <AgentText text={cite.quote} className="min-w-0 flex-1 text-cell leading-[1.5] text-ink" />
        {onOpenDialog !== undefined && (
          <button
            type="button"
            aria-label="Open citation…"
            aria-haspopup="dialog"
            className={GHOST}
            onClick={() => {
              onOpenDialog(cite);
            }}
          >
            <Icon name="square-arrow-out-up-right" size={13} />
          </button>
        )}
      </div>
      <div className="flex items-center gap-[6px] px-[15px] pb-[13px] text-pill-sm font-normal text-ink-3">
        <span data-cite="loc" className="min-w-0 flex-1 truncate">
          {cite.loc}
        </span>
        {many ? (
          <span className="flex flex-none items-center gap-[2px]">
            <button
              type="button"
              aria-label="Previous source"
              disabled={payload.index === 0}
              className={GHOST}
              onClick={() => onStep?.(payload.index - 1)}
            >
              <Icon name="chevron-left" size={12} />
            </button>
            <span className="tabular-nums">{`${String(payload.index + 1)} of ${String(payload.list.length)}`}</span>
            <button
              type="button"
              aria-label="Next source"
              disabled={payload.index === payload.list.length - 1}
              className={GHOST}
              onClick={() => onStep?.(payload.index + 1)}
            >
              <Icon name="chevron-right" size={12} />
            </button>
          </span>
        ) : (
          <span className="flex-none">1 citation</span>
        )}
      </div>
    </div>
  );
}

export interface CitationPopoverHostProps {
  onOpenDialog?: (cite: CitationView) => void;
}

/** The E2 host with the C-07 popover in it: place once per page or scope. */
export function CitationPopoverHost({ onOpenDialog }: CitationPopoverHostProps): JSX.Element {
  const store = useMatchStore();
  return (
    <AnchoredPopoverHost
      render={(payload) => (
        <CitationPopover
          payload={payload}
          {...(onOpenDialog === undefined ? {} : { onOpenDialog })}
          onStep={(index) => {
            const next = payload.list[index];
            if (next === undefined) return;
            store.retarget(citationMatch(next), { list: payload.list, index });
          }}
        />
      )}
    />
  );
}

// ---- CitationChip and footer --------------------------------------------------------------------

export interface ProcedureRef {
  ref: string;
  title: string;
}

export type CitationChipProps =
  | {
      kind: "citations";
      citations: readonly CitationView[];
      forceState?: "hover" | "open";
    }
  | {
      kind: "procedures";
      procedures: readonly ProcedureRef[];
      forceState?: "hover" | "open";
    };

const CHIP = cn(
  "inline-flex h-[28px] items-center gap-[7px] rounded-pill bg-card px-[12px] text-cell font-medium text-ink shadow-e1",
  "hover:bg-nested data-[force=hover]:bg-nested data-[state=open]:bg-nested",
  PRESS,
);
const MENU =
  "flex max-h-[300px] w-[280px] flex-col gap-[1px] overflow-y-auto rounded-pane bg-card p-[4px] shadow-menu outline-none";
const ITEM =
  "flex h-[32px] cursor-default items-center gap-[8px] rounded-tile px-[10px] text-body text-ink outline-offset-[-2px] select-none data-[highlighted]:bg-nav-fill";

function MenuRow({ name, location }: { name: string; location: string }): JSX.Element {
  return (
    <>
      <span className="min-w-0 flex-1 truncate">{name}</span>
      <span className="max-w-[46%] flex-none truncate text-cell text-ink-3">{location}</span>
    </>
  );
}

/** The footer chip: "Citations (n)" or "Procedures (n)", opening a 280 menu upward. Hovering or
 * focusing a citation row lights its match; choosing it pins its popover. */
export function CitationChip(props: CitationChipProps): JSX.Element {
  const store = useMatchStore();
  const [trigger, setTrigger] = useState<HTMLButtonElement | null>(null);
  const count = props.kind === "citations" ? props.citations.length : props.procedures.length;
  const label = props.kind === "citations" ? "Citations" : "Procedures";
  const button = (
    <button
      type="button"
      ref={setTrigger}
      data-cite="chip"
      {...forceAttr(props.forceState === "hover" ? "hover" : undefined)}
      className={CHIP}
    >
      <Icon name={props.kind === "citations" ? "file-text" : "notebook-text"} size={12} />
      {`${label} (${String(count)})`}
    </button>
  );
  const rows: ReactNode =
    props.kind === "citations"
      ? props.citations.map((cite, index) => {
          const id = citationMatch(cite);
          const payload: CitationPayload = { list: props.citations, index };
          return (
            <DropdownMenu.Item
              key={cite.n}
              className={ITEM}
              onFocus={() => {
                if (id !== null) store.light(id, trigger);
              }}
              onPointerLeave={() => {
                store.release("row");
              }}
              onSelect={() => {
                store.togglePin(id, trigger, payload);
              }}
            >
              <MenuRow name={cite.title} location={cite.loc} />
            </DropdownMenu.Item>
          );
        })
      : props.procedures.map((p) => (
          <DropdownMenu.Item key={p.ref} className={ITEM}>
            <MenuRow name={p.title} location={p.ref} />
          </DropdownMenu.Item>
        ));
  if (props.forceState === "open") {
    return (
      <span className="relative inline-flex">
        <span data-state="open" className="contents">
          {button}
        </span>
        <div
          role="menu"
          aria-label={label}
          className={cn(MENU, "absolute bottom-[calc(100%+8px)] left-0 z-10")}
        >
          {(props.kind === "citations"
            ? props.citations.map((c) => ({ key: String(c.n), name: c.title, location: c.loc }))
            : props.procedures.map((p) => ({ key: p.ref, name: p.title, location: p.ref }))
          ).map((row) => (
            <div key={row.key} role="menuitem" tabIndex={-1} className={ITEM}>
              <MenuRow name={row.name} location={row.location} />
            </div>
          ))}
        </div>
      </span>
    );
  }
  return (
    <DropdownMenu.Root
      onOpenChange={(open) => {
        if (!open) store.release("row");
      }}
    >
      <DropdownMenu.Trigger asChild>{button}</DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          side="top"
          align="start"
          sideOffset={8}
          aria-label={label}
          className={MENU}
        >
          {rows}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

/** The pinned footer of a workpaper: the chips, padded 11 14 on white with a hair above; `bare`
 * drops the padding, rule and fill (when a pane's footer already draws them). */
export function CitationFooter({
  bare = false,
  children,
}: {
  bare?: boolean;
  children: ReactNode;
}): JSX.Element {
  return (
    <div
      data-cite="footer"
      className={cn(
        "flex items-center gap-[8px]",
        !bare && "bg-card px-[14px] py-[11px] hairline-t",
      )}
    >
      {children}
    </div>
  );
}
