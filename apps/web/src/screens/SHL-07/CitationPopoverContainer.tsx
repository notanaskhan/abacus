// SHL-07 Citation popover, the L3 container (P-03-T11; C4 §3.2; SPEC-322 AC-6 to AC-12): a cited
// cell reads its anchor's stack from `GET /v1/citations` and opens the 372 popover (420 for the
// methodology guidance) through the E1 match store and the E2 anchored host (F-05-T41).
//
// - Hover intent is 150 ms (DF-38): the preview renders at 95% opacity and closes 140 ms after the
//   pointer leaves. A click pins it and the cell keeps its ring; Escape closes the topmost layer,
//   the purple fades over 360 ms and focus returns to the cell.
// - `title` and `loc` are the server's, rendered by code from the locator (INV-2). A document
//   quote goes through AgentText; the firm's program text renders as plain text.
// - An unverified citation never renders as fact: the body says "Unverified" and no quote is
//   styled as a finding (INV-2, AC-12).
// - A moved citation says what superseded it, in the danger ink, with Re-link… only when the
//   server offers `citation.relink` (AC-10). Purple is for tracing only.
// - The popover is local state, never in the URL (chapter 04 §2.4).

import { type CitationV2Out, viewerPage } from "@abacus/api-client";
import { listCitationsOptions, relinkCitationMutation } from "@abacus/api-client/query";
import {
  AgentText,
  AnchoredPopoverHost,
  Button,
  type CitationPayload,
  type CitationView,
  Icon,
  MATCH_CELL,
  type MatchId,
  type MatchState,
  contractMatchId,
  date,
  useMatchStore,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type JSX,
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { COPY } from "./copy";

/** DF-38: a hover lights and previews after 150 ms; it goes dark 140 ms after leaving. */
export const HOVER_INTENT_MS = 150;
export const POPOVER_WIDTH = { citation: 372, guidance: 420 } as const;
export type PopoverVariant = keyof typeof POPOVER_WIDTH;

/** A C4 citation as the C-07 match store carries it, with the display the card needs. */
export interface Shl07Cite extends CitationView {
  out: CitationV2Out;
}

/** What a cell cites: its anchor in C4 terms (DEC-265). */
export interface CitationAnchorRef {
  type: string;
  id: string;
  ref: string;
}

function matchOf(out: CitationV2Out): MatchId | null {
  return out.match_id === null
    ? null
    : contractMatchId({ match_id: out.match_id, kind: out.kind });
}

export function toCiteViews(items: readonly CitationV2Out[]): Shl07Cite[] {
  return items.map((out) => ({
    n: out.n,
    title: out.title,
    quote: out.quote ?? "",
    loc: out.loc,
    match: matchOf(out),
    out,
  }));
}

function citeOf(view: CitationView | undefined): Shl07Cite | undefined {
  return view !== undefined && "out" in view ? (view as Shl07Cite) : undefined;
}

// ---- The cited cell -----------------------------------------------------------------------------

export interface CitedCellProps {
  anchor: CitationAnchorRef;
  /** The element: a table cell by default. */
  as?: "td" | "span" | "button";
  /** Open on mount, as an artboard opens: pinned, or as a hover preview. */
  openOnMount?: "pin" | "hover";
  className?: string;
  children: ReactNode;
}

/** A cell with citations: hover previews, click pins, Escape closes and refocuses it. */
export function CitedCell({
  anchor,
  as: Tag = "td",
  openOnMount,
  className,
  children,
}: CitedCellProps): JSX.Element {
  const store = useMatchStore();
  const ref = useRef<HTMLElement | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { data } = useQuery(
    listCitationsOptions({
      query: { anchor_type: anchor.type, anchor_id: anchor.id, anchor_ref: anchor.ref },
    }),
  );
  const list = useMemo(() => toCiteViews(data?.items ?? []), [data]);
  const mine = useSyncExternalStore(
    store.subscribe,
    () => {
      const s = store.get();
      return s.payload !== null && s.origin !== null && s.origin === ref.current;
    },
    () => false,
  );
  const pinned = useSyncExternalStore(
    store.subscribe,
    () => mine && store.get().pinned,
    () => false,
  );
  useEffect(
    () => () => {
      if (timer.current !== null) clearTimeout(timer.current);
    },
    [],
  );
  const payload = (): CitationPayload => ({ list, index: 0 });
  const first = list[0];
  const opened = useRef(false);
  useEffect(() => {
    if (openOnMount === undefined || opened.current || first === undefined) return;
    opened.current = true;
    const at = { list, index: 0 };
    if (openOnMount === "pin") store.togglePin(first.match, ref.current, at);
    else store.light(first.match, ref.current, at);
  }, [openOnMount, first, list, store]);
  const cancel = (): void => {
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = null;
  };
  const preview = (el: HTMLElement): void => {
    cancel();
    if (first === undefined || store.get().pinned) return;
    timer.current = setTimeout(() => {
      timer.current = null;
      if (!store.get().pinned) store.light(first.match, el, payload());
    }, HOVER_INTENT_MS);
  };
  const leave = (): void => {
    cancel();
    if (!store.get().pinned) store.release("cell");
  };
  const Element = Tag as "td";
  return (
    <Element
      ref={(el: HTMLElement | null) => {
        ref.current = el;
      }}
      data-cited=""
      data-match={first?.match ?? undefined}
      {...(mine ? { "data-lit": "" } : {})}
      {...(pinned ? { "data-pinned": "" } : {})}
      tabIndex={0}
      aria-haspopup="dialog"
      aria-expanded={mine}
      className={`${MATCH_CELL} cursor-pointer outline-offset-[-2px] ${className ?? ""}`}
      onPointerEnter={(event) => {
        preview(event.currentTarget);
      }}
      onPointerLeave={leave}
      onFocus={(event) => {
        if (event.currentTarget.matches(":focus-visible")) preview(event.currentTarget);
      }}
      onBlur={leave}
      onClick={(event) => {
        cancel();
        if (first !== undefined) store.togglePin(first.match, event.currentTarget, payload());
      }}
      onKeyDown={(event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        cancel();
        if (first !== undefined) store.togglePin(first.match, event.currentTarget, payload());
      }}
    >
      {children}
    </Element>
  );
}

// ---- The card -----------------------------------------------------------------------------------

const GHOST =
  "inline-flex size-[22px] flex-none items-center justify-center rounded-pill text-ink-3 hover:bg-nav-fill hover:text-ink disabled:text-ink-4 disabled:hover:bg-transparent";

/** The region a document match lights, in page points, from the server's match id. */
export function regionOf(matchId: string | null): { page: number; box: readonly number[] } | null {
  const found =
    matchId === null ? null : /#p(\d+):([\d.]+),([\d.]+),([\d.]+),([\d.]+)$/.exec(matchId);
  if (found === null) return null;
  return {
    page: Number(found[1]),
    box: [Number(found[2]), Number(found[3]), Number(found[4]), Number(found[5])],
  };
}

const THUMB_W = 120;
const THUMB_H = 80;
const PAGE_PT = 612;

/** A 120×80 masked thumbnail of the cited page, cropped to the region (AC-7). */
function PageThumb({ out }: { out: CitationV2Out }): JSX.Element | null {
  const version = out.source.evidence_version_id;
  const region = regionOf(out.match_id);
  const page = region?.page ?? out.source.page;
  const { data } = useQuery({
    queryKey: ["shl07-thumb", version, page],
    enabled: version !== null && page !== null,
    gcTime: 0,
    queryFn: async () =>
      (
        await viewerPage({
          path: { version_id: version ?? "", page_no: page ?? 1 },
          parseAs: "blob",
          throwOnError: true,
        })
      ).data,
  });
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    if (!(data instanceof Blob)) return;
    const url = URL.createObjectURL(data);
    setSrc(url);
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [data]);
  if (version === null || page === null) return null;
  const box = region?.box ?? [0, 0, PAGE_PT, PAGE_PT * (THUMB_H / THUMB_W)];
  const [x0 = 0, top = 0, x1 = PAGE_PT, bottom = 0] = box;
  const scale = Math.min(THUMB_W / Math.max(x1 - x0, 1), 1);
  const style = {
    width: PAGE_PT * scale,
    left: -x0 * scale,
    top: (THUMB_H - (bottom - top) * scale) / 2 - top * scale,
  };
  return (
    <div
      data-cite="thumb"
      className="relative h-[80px] w-[120px] flex-none overflow-hidden rounded-tile bg-nested inset-shadow-hair"
    >
      {src !== null && (
        <img
          src={src}
          alt={COPY.popover.thumb(page)}
          className="absolute max-w-none"
          style={style}
        />
      )}
    </div>
  );
}

function movedLine(out: CitationV2Out): string | null {
  if (out.moved === null) return null;
  const ref = out.title.split(":")[0] ?? out.title;
  const on = date(out.moved.at, { withYear: true, now: new Date(out.moved.at) });
  return COPY.popover.moved(ref, out.source.version ?? "", out.moved.successor_ref ?? "", on);
}

export interface CitationCardProps {
  payload: CitationPayload;
  state: MatchState<CitationPayload>;
  variant: PopoverVariant;
  onStep: (index: number) => void;
  /** Re-link a moved citation (P-03-T12); offered only when the server allows it. */
  onRelink?: (citation: CitationV2Out) => void;
  /** Open a document citation in the source viewer (SHL-08). */
  onOpenSource?: (citation: CitationV2Out) => void;
}

/** One source of the stack: header, body and footer as SHL-07 draws them. */
export function CitationCard({
  payload,
  state,
  variant,
  onStep,
  onRelink,
  onOpenSource,
}: CitationCardProps): JSX.Element | null {
  const cite = citeOf(payload.list[payload.index]);
  if (cite === undefined) return null;
  const { out } = cite;
  const count = payload.list.length;
  const many = count > 1;
  const guidance = variant === "guidance";
  const document = out.kind === "document_text" || out.kind === "sheet_cell";
  const heading = document && out.loc !== "" ? `${out.title} · ${out.loc}` : out.title;
  const moved = out.state === "moved" ? movedLine(out) : null;
  const relink = out.allowed_actions.includes("citation.relink") && onRelink !== undefined;
  const headingId = `shl07-${out.id}`;
  return (
    <div
      data-cite="card"
      data-heading={headingId}
      data-variant={variant}
      data-pinned={state.pinned ? "" : undefined}
      className={state.pinned ? "flex flex-col" : "flex flex-col opacity-95"}
    >
      <div className="flex items-start gap-[8px] px-[15px] pt-[13px] pb-[12px] hairline-b">
        <p
          id={headingId}
          className="min-w-0 flex-1 text-section leading-[1.3] font-medium tracking-[-0.012em]"
        >
          {heading}
        </p>
        {many && (
          <span className="flex flex-none items-center gap-[2px] text-pill-sm text-ink-2">
            <button
              type="button"
              aria-label={COPY.popover.previous}
              disabled={payload.index === 0}
              className={GHOST}
              onClick={() => {
                onStep(payload.index - 1);
              }}
            >
              <Icon name="chevron-left" size={12} />
            </button>
            <span
              className="tabular-nums"
              aria-live="polite"
              aria-label={COPY.popover.announce(payload.index + 1, count)}
            >
              {COPY.popover.stepper(payload.index + 1, count)}
            </span>
            <button
              type="button"
              aria-label={COPY.popover.next}
              disabled={payload.index === count - 1}
              className={GHOST}
              onClick={() => {
                onStep(payload.index + 1);
              }}
            >
              <Icon name="chevron-right" size={12} />
            </button>
          </span>
        )}
      </div>
      <div className="flex gap-[10px] px-[15px] pt-[12px] pb-[10px]">
        {!guidance && (
          <Icon name="file-text" size={14} className="mt-[2px] flex-none text-ink-3" />
        )}
        <div className="flex min-w-0 flex-1 flex-col gap-[8px]">
          {!out.verified ? (
            <p data-cite="unverified" className="text-cell leading-[1.5] text-ink-3">
              {COPY.popover.unverified}
            </p>
          ) : document ? (
            <AgentText text={out.quote ?? ""} className="text-cell leading-[1.5] text-ink" />
          ) : (
            <p data-cite="program-text" className="text-cell leading-[1.5] text-ink">
              {out.quote ?? ""}
            </p>
          )}
          {moved !== null && (
            <p data-cite="moved" className="text-body text-danger">
              {moved}
            </p>
          )}
          {moved !== null && relink && (
            <span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  onRelink(out);
                }}
              >
                {COPY.popover.relink}
              </Button>
            </span>
          )}
        </div>
        {document && out.verified && out.source.evidence_version_id !== null && (
          <PageThumb out={out} />
        )}
        {document && onOpenSource !== undefined && out.verified && (
          <button
            type="button"
            aria-label={COPY.popover.openSource}
            className={GHOST}
            onClick={() => {
              onOpenSource(out);
            }}
          >
            <Icon name="arrow-up-right" size={13} />
          </button>
        )}
      </div>
      {!guidance && (
        <p data-cite="footer" className="px-[15px] pb-[13px] text-pill-sm text-ink-3">
          {COPY.popover.footer(count)}
        </p>
      )}
      {many && (
        // The stack's two ghost edges, peeking 4 and 8 px below the card (SHL-07b).
        <div aria-hidden="true" data-cite="ghost-edges" className="flex flex-col items-center">
          <span data-ghost-edge="4" className="h-[4px] w-[calc(100%-12px)] bg-nested hairline-t" />
          <span
            data-ghost-edge="8"
            className="h-[4px] w-[calc(100%-24px)] bg-nav-fill hairline-t"
          />
        </div>
      )}
    </div>
  );
}

// ---- The host -----------------------------------------------------------------------------------

export interface CitationPopoverContainerProps {
  variant?: PopoverVariant;
  onRelink?: (citation: CitationV2Out) => void;
  onOpenSource?: (citation: CitationV2Out) => void;
}

/** The E2 host with the SHL-07 card: place once per scope, beside the cited cells. */
export function CitationPopoverContainer({
  variant = "citation",
  onRelink,
  onOpenSource,
}: CitationPopoverContainerProps): JSX.Element {
  const store = useMatchStore();
  const queries = useQueryClient();
  // Re-link (P-03-T12 serves it): a person re-verifies on the successor; the stack re-reads.
  const relink = useMutation({
    ...relinkCitationMutation(),
    onSettled: () => queries.invalidateQueries({ queryKey: [{ _id: "listCitations" }] }),
  });
  const onRelinkOr =
    onRelink ??
    ((citation: CitationV2Out) => {
      relink.mutate({ path: { citation_id: citation.id } });
    });
  return (
    <AnchoredPopoverHost
      width={POPOVER_WIDTH[variant]}
      label={COPY.popover.label}
      render={(payload, state) => (
        <CitationCard
          payload={payload}
          state={state}
          variant={variant}
          onRelink={onRelinkOr}
          {...(onOpenSource === undefined ? {} : { onOpenSource })}
          onStep={(index) => {
            const next = payload.list[index];
            if (next !== undefined) store.retarget(next.match, { list: payload.list, index });
          }}
        />
      )}
    />
  );
}
