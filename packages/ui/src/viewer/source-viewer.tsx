import { type JSX, type ReactNode, useEffect, useId, useRef, useState } from "react";
import { cn } from "../cn";
import { Menu, type MenuItem } from "../components/popover";
import { Skeleton } from "../components/states";
import { Icon, type IconName } from "../icons";
import { registryWord } from "../status";
import { MATCH_REGION, useMatch, useMatchState, useMatchStore } from "../tracing/match";
import type {
  LinkedFigure,
  PtRect,
  RevealedValue,
  ViewerFile,
  ViewerMask,
  ViewerPage,
  ViewerRegion,
  ViewerStatus,
} from "./types";
import type { MatchId } from "../tracing/types";

// E5 SourceViewer shell (F-05-T47; C-08 Doc Kit, plan F-05 G3). Hostile content (ADR-052): pages
// are the server's rendered, masked page images and nothing else. No pdf.js, no SheetJS, no raw
// client file, and no client string ever reaches the DOM as HTML: the file name, region labels,
// mask tokens and a revealed value are text nodes. A page source that is not a same-origin path, a
// blob or a PNG data URL is refused and the page says so.
//
// Two variants: `full` (a pane: the centred header and the four-capsule toolbar
// `[− Fit + ⟳] [˄ 1 / n ˅] [● ⌄] [⌕]`) and `evidence` (the narrow audit bar). Download is never in
// a bar; it can only be an item of the ⋯ menu the caller supplies. Regions are invisible until
// their match is lit (E1 MatchProvider). A masked field carries the reveal slot: one explicit
// click calls the caller's logged reveal once (P-03 owns the endpoint and the audit event).

export const VIEWER_ZOOM = { min: 0.5, max: 2, step: 0.25 } as const;

/** Room a linked figure tag needs on a region's right before it flips left (C-08). */
export const TAG_ROOM_PX = 170;

/** Where a lit region comes to rest when the viewer scrolls to it: 30% from the well's top (SHL-08
 * interactions; P-03 AC3.1). */
export const LIT_AT = 0.3;

/** The well's scrollTop that puts a region whose top is `regionTop` (viewport px) at `LIT_AT` of the
 * well's height, given the well's own top and height and its current scrollTop. Never negative. */
export function litScrollTop(
  scrollTop: number,
  wellTop: number,
  wellHeight: number,
  regionTop: number,
): number {
  return Math.max(0, Math.round(scrollTop + (regionTop - wellTop) - LIT_AT * wellHeight));
}

/** Only the server's page images: a same-origin path, a blob, or a PNG data URL (fixtures). */
export function pageSrcAllowed(src: string): boolean {
  if (src.startsWith("/") && !src.startsWith("//")) return true;
  if (src.startsWith("blob:")) return true;
  return /^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(src);
}

export interface RevealSlot {
  /** The viewer holds `pii.reveal` (C4 `allowed_actions`); offshore members never do. */
  allowed: boolean;
  /** Called once per explicit click with the mask's id; the caller posts the logged reveal. */
  onReveal: (maskId: string) => void;
  /** Values the caller has revealed, by mask id. */
  revealed?: Readonly<Record<string, RevealedValue>>;
  /** "Reveal (logged)" */
  label?: string;
}

export interface SourceViewerProps {
  file: ViewerFile;
  variant?: "full" | "evidence";
  status?: ViewerStatus;
  /** Skeleton page blocks while the manifest or a page loads. */
  loading?: boolean;
  /** The ⋯ menu ("Download", "Open in Files"). Never drawn in a bar. */
  menu?: readonly MenuItem[];
  reveal?: RevealSlot;
  /** The page's width at 100%, px. */
  pageWidth?: number;
  /** A fixed height for the shell, px; it fills its parent otherwise. */
  height?: number;
  className?: string;
  /** The full variant's centred name header. A host that draws the name itself (the O2 drawer's
   * own header) turns it off. */
  header?: boolean;
  /** Skeleton pages while loading: 2 by default, 3 for SHL-08e. */
  skeletons?: number;
  /** Auto-highlight cited fields (SHL-08h): every region marked `cited` carries a 1px match-line
   * outline with no fill until it is lit. */
  outlineCited?: boolean;
  /** Scroll the well so the lit region sits `LIT_AT` from its top, and move the page count to its
   * page (SHL-08: a match lit from outside the viewer, or by a figure row). */
  scrollToLit?: boolean;
  /** The multi-source stack motif: page edges peek 6px (and 12px) under the page holding this
   * match's region, each with a match-mark band level with the region. */
  stack?: { match: MatchId; edges: 1 | 2 };
  /** Above the well, under the bar (the SHL-08 linked-figure card). */
  aboveWell?: ReactNode;
  /** In the well, after the pages (the SHL-08 "Also cited" caption). */
  afterPages?: ReactNode;
}

// ---- Toolbar ----------------------------------------------------------------------------------------

const CAPSULE = "inline-flex items-center gap-[2px] rounded-pill bg-card p-[3px] shadow-e1";
const TOOL =
  "inline-flex h-[26px] min-w-[27px] items-center justify-center gap-[4px] rounded-pill px-[5px] text-body text-ink hover:bg-nested disabled:text-ink-4 disabled:hover:bg-transparent";

function Tool({
  icon,
  label,
  onClick,
  disabled = false,
  children,
}: {
  icon?: IconName;
  label: string;
  onClick?: () => void;
  disabled?: boolean;
  children?: ReactNode;
}): JSX.Element {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className={TOOL}
    >
      {icon !== undefined && <Icon name={icon} size={13} />}
      {children}
    </button>
  );
}

function MoreMenu({ items, label }: { items: readonly MenuItem[]; label: string }): JSX.Element {
  return (
    <Menu
      label={label}
      width={180}
      sections={[[...items]]}
      trigger={
        <button
          type="button"
          aria-label={label}
          className="inline-flex size-[26px] items-center justify-center rounded-pill text-ink-2 hover:bg-nested data-[state=open]:bg-nested"
        >
          <Icon name="ellipsis" size={14} />
        </button>
      }
    />
  );
}

// ---- Regions, tags and masks -----------------------------------------------------------------------

function box(
  rect: PtRect,
  page: ViewerPage,
): { left: string; top: string; width: string; height: string } {
  const [x0, top, x1, bottom] = rect;
  const pct = (n: number, of: number): string => `${String((n / of) * 100)}%`;
  return {
    left: pct(x0, page.width_pt),
    top: pct(top, page.height_pt),
    width: pct(x1 - x0, page.width_pt),
    height: pct(bottom - top, page.height_pt),
  };
}

function Tag({
  figure,
  rect,
  page,
  widthPx,
  zoom,
}: {
  figure: LinkedFigure;
  rect: PtRect;
  page: ViewerPage;
  widthPx: number;
  zoom: number;
}): JSX.Element {
  const [, top, x1, bottom] = rect;
  const room = widthPx * (1 - x1 / page.width_pt) > TAG_ROOM_PX;
  const centre = `${String(((top + bottom) / 2 / page.height_pt) * 100)}%`;
  const edge = `${String((x1 / page.width_pt) * 100)}%`;
  const left = `${String((rect[0] / page.width_pt) * 100)}%`;
  return (
    <span
      data-linked-figure={room ? "right" : "left"}
      style={{
        top: centre,
        ...(room ? { left: edge } : { right: `calc(100% - ${left})` }),
        transform: `translateY(-50%) scale(${String(1 / zoom)})`,
        transformOrigin: room ? "left center" : "right center",
      }}
      className={cn(
        "pointer-events-none absolute z-[2] flex items-center motion-rise",
        room ? "flex-row" : "flex-row-reverse",
      )}
    >
      <span aria-hidden="true" className="w-[12px] border-t border-dashed border-match-line" />
      <span className="inline-flex h-[22px] items-center gap-[6px] rounded-pill bg-card px-[8px] text-meta whitespace-nowrap shadow-e1">
        <span className="text-ink-2">{figure.label}</span>
        <span className="font-medium text-match-ink">{figure.value}</span>
      </span>
    </span>
  );
}

function Region({
  region,
  page,
  widthPx,
  zoom,
  outline,
}: {
  region: ViewerRegion;
  page: ViewerPage;
  widthPx: number;
  zoom: number;
  outline: boolean;
}): JSX.Element {
  const { bind, lit, pin } = useMatch(region.match, "region");
  return (
    <>
      {region.rects.map((rect) => (
        <span
          key={rect.join(",")}
          aria-hidden="true"
          {...bind}
          data-match-kind="region"
          {...(region.band === true ? { "data-band": "" } : {})}
          {...(outline && region.cited === true && !lit ? { "data-outlined": "" } : {})}
          onClick={(e) => {
            pin(e.currentTarget);
          }}
          style={box(rect, page)}
          className={cn(
            "absolute z-[1] cursor-pointer",
            region.band === true
              ? "transition-[background-color,box-shadow] duration-[360ms] ease-out data-[lit]:bg-match-soft data-[lit]:shadow-[inset_0_1px_0_var(--color-match-line),inset_0_-1px_0_var(--color-match-line)]"
              : cn(MATCH_REGION, "rounded-[2px]"),
            "data-[outlined]:inset-ring-1 data-[outlined]:inset-ring-match-line",
          )}
        />
      ))}
      {lit && region.linkedFigure !== undefined && region.rects[0] !== undefined && (
        <Tag
          figure={region.linkedFigure}
          rect={region.rects[0]}
          page={page}
          widthPx={widthPx}
          zoom={zoom}
        />
      )}
    </>
  );
}

function Mask({
  mask,
  page,
  reveal,
}: {
  mask: ViewerMask;
  page: ViewerPage;
  reveal: RevealSlot | undefined;
}): JSX.Element {
  const shown = reveal?.revealed?.[mask.id];
  const labelId = useId();
  return (
    <span
      data-mask={mask.kind}
      style={box(mask.rect, page)}
      className="absolute z-[3] flex items-center"
    >
      <span className="flex items-center gap-[6px] rounded-value bg-card px-[6px] py-[2px] text-meta shadow-e1">
        <span id={labelId} className="font-medium whitespace-nowrap">
          {shown === undefined ? mask.display : shown.value}
        </span>
        {shown === undefined && reveal?.allowed === true && (
          <button
            type="button"
            aria-describedby={labelId}
            onClick={() => {
              reveal.onReveal(mask.id);
            }}
            className="rounded-pill px-[4px] text-meta whitespace-nowrap text-ink-2 underline decoration-ink-4 underline-offset-2 hover:text-ink"
          >
            {reveal.label ?? "Reveal (logged)"}
          </button>
        )}
        {shown !== undefined && (
          <span data-reveal-note="" className="whitespace-nowrap text-ink-3">
            {shown.note}
          </span>
        )}
      </span>
    </span>
  );
}

function Page({
  page,
  total,
  file,
  widthPx,
  zoom,
  rotation,
  reveal,
  outline,
  stack,
}: {
  page: ViewerPage;
  total: number;
  file: ViewerFile;
  widthPx: number;
  zoom: number;
  rotation: number;
  reveal: RevealSlot | undefined;
  outline: boolean;
  stack: { match: MatchId; edges: 1 | 2 } | undefined;
}): JSX.Element {
  // A page whose image is still on its way ("") is drawn blank with its regions: the geometry is
  // the manifest's, so a lit region can be scrolled to before the image arrives.
  const pending = page.src === "";
  const ok = pending || pageSrcAllowed(page.src);
  const w = widthPx * zoom;
  const h = (w * page.height_pt) / page.width_pt;
  const turn = (page.rotation + rotation) % 360;
  const anchor =
    stack === undefined
      ? undefined
      : file.regions.find((r) => r.page === page.n && r.match === stack.match)?.rects[0];
  const sheet = (
    <div
      data-page={page.n}
      style={{
        width: w,
        height: h,
        transform: turn === 0 ? undefined : `rotate(${String(turn)}deg)`,
      }}
      className="relative flex-none bg-card shadow-page"
    >
      {pending ? null : ok ? (
        <img
          src={page.src}
          alt={`Page ${String(page.n)} of ${String(total)}`}
          draggable={false}
          decoding="async"
          referrerPolicy="no-referrer"
          className="absolute inset-0 size-full select-none"
        />
      ) : (
        <p
          role="img"
          aria-label={`Page ${String(page.n)} of ${String(total)}`}
          className="p-[16px] text-dense text-ink-3"
        >
          {registryWord("viewer", "not_previewable").label}
        </p>
      )}
      {ok &&
        file.regions
          .filter((r) => r.page === page.n)
          .map((r) => (
            <Region
              key={r.match}
              region={r}
              page={page}
              widthPx={w}
              zoom={zoom}
              outline={outline}
            />
          ))}
      {ok &&
        (file.masks ?? [])
          .filter((m) => m.page === page.n)
          .map((m) => <Mask key={m.id} mask={m} page={page} reveal={reveal} />)}
    </div>
  );
  if (anchor === undefined || stack === undefined) return sheet;
  const band = box(anchor, page);
  return (
    <div
      data-stack={stack.edges}
      style={{ width: w + 6 * stack.edges, height: h + 6 * stack.edges }}
      className="relative flex-none"
    >
      {Array.from({ length: stack.edges }, (_, i) => stack.edges - i).map((k) => (
        <span
          key={k}
          aria-hidden="true"
          data-stack-edge={k}
          style={{ top: 6 * k, left: 6 * k, width: w, height: h }}
          className="absolute overflow-hidden bg-card shadow-page"
        >
          <span
            style={{ top: band.top, height: band.height }}
            className="absolute inset-x-0 bg-match-mark"
          />
        </span>
      ))}
      <div className="absolute top-0 left-0">{sheet}</div>
    </div>
  );
}

// ---- Shell ----------------------------------------------------------------------------------------

function StatusPane({ status }: { status: ViewerStatus }): JSX.Element {
  const word = registryWord("viewer", status).label;
  return (
    <div
      role="status"
      className="flex flex-1 flex-col items-center justify-center gap-[8px] p-[24px]"
    >
      <span className="inline-flex size-[30px] items-center justify-center rounded-tile bg-nested text-ink-3">
        <Icon
          name={
            status === "password_protected" ? "lock" : status === "processing" ? "clock" : "file-x"
          }
          size={15}
        />
      </span>
      <p className="text-body font-medium">{word}</p>
    </div>
  );
}

export function SourceViewer({
  file,
  variant = "full",
  status = "ready",
  loading = false,
  menu,
  reveal,
  pageWidth,
  height,
  className,
  header = true,
  skeletons = 2,
  outlineCited = false,
  scrollToLit = false,
  stack,
  aboveWell,
  afterPages,
}: SourceViewerProps): JSX.Element {
  const evidence = variant === "evidence";
  const widthPx = pageWidth ?? (evidence ? 400 : 600);
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [at, setAt] = useState(1);
  const [finding, setFinding] = useState(false);
  const [query, setQuery] = useState("");
  const well = useRef<HTMLDivElement>(null);
  const store = useMatchStore();
  const state = useMatchState();
  const total = file.pages.length;
  const ready = status === "ready" && !loading;

  // Scroll the lit region to LIT_AT once per match and per set of page images (the regions are
  // drawn as soon as the manifest is, so this runs before the images arrive).
  const litPage = file.regions.find((r) => r.match === state.id)?.page;
  const scrolled = useRef<string | null>(null);
  useEffect(() => {
    if (!scrollToLit || state.id === null || litPage === undefined || !ready) return;
    const key = `${state.id}@${String(zoom)}`;
    if (scrolled.current === key) return;
    const el = well.current;
    const target = Array.from(
      el?.querySelectorAll<HTMLElement>('[data-match-kind="region"]') ?? [],
    ).find((r) => r.getAttribute("data-match") === state.id);
    if (el === null || target === undefined) return;
    scrolled.current = key;
    setAt(litPage);
    const frame = el.getBoundingClientRect();
    el.scrollTop = litScrollTop(
      el.scrollTop,
      frame.top,
      el.clientHeight,
      target.getBoundingClientRect().top,
    );
  }, [scrollToLit, state.id, litPage, ready, zoom]);

  const zoomBy = (d: number): void => {
    setZoom((z) =>
      Math.min(
        VIEWER_ZOOM.max,
        Math.max(VIEWER_ZOOM.min, Math.round((z + d * VIEWER_ZOOM.step) * 100) / 100),
      ),
    );
  };
  const goTo = (n: number): void => {
    const next = Math.min(total, Math.max(1, n));
    setAt(next);
    well.current
      ?.querySelector<HTMLElement>(`[data-page="${String(next)}"]`)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const find = (): void => {
    const q = query.trim().toLowerCase();
    if (q === "") return;
    const hit = file.regions.find((r) => (r.label ?? "").toLowerCase().includes(q));
    if (hit === undefined) return;
    if (state.id !== hit.match || !state.pinned) store.togglePin(hit.match, null);
  };
  const fitLabel = zoom === 1 ? "Fit" : `${String(Math.round(zoom * 100))}%`;
  const zoomCapsule = (
    <span className={CAPSULE}>
      <Tool
        icon={evidence ? "minus" : "zoom-out"}
        label="Zoom out"
        disabled={zoom <= VIEWER_ZOOM.min}
        onClick={() => {
          zoomBy(-1);
        }}
      />
      <Tool
        label="Fit to width"
        onClick={() => {
          setZoom(1);
        }}
      >
        {fitLabel}
      </Tool>
      <Tool
        icon={evidence ? "plus" : "zoom-in"}
        label="Zoom in"
        disabled={zoom >= VIEWER_ZOOM.max}
        onClick={() => {
          zoomBy(1);
        }}
      />
      <Tool
        icon="rotate-cw"
        label="Rotate"
        onClick={() => {
          setRotation((r) => (r + 90) % 360);
        }}
      />
    </span>
  );
  const pageCount = (
    <span className="px-[4px] text-body tabular-nums" aria-live="polite">
      {at}
      <span className="text-ink-2">{` / ${String(total)}`}</span>
    </span>
  );
  const menuLabel = `More for ${file.name}`;

  const bar = evidence ? (
    <div
      data-viewer-bar="evidence"
      className="flex h-[44px] flex-none items-center gap-[7px] px-[10px]"
    >
      {zoomCapsule}
      <span className={CAPSULE}>{pageCount}</span>
      <span className="min-w-0 flex-1 truncate text-body font-medium">{file.name}</span>
      {menu !== undefined && menu.length > 0 && <MoreMenu items={menu} label={menuLabel} />}
    </div>
  ) : (
    <>
      {header && (
        <div className="relative flex h-[46px] flex-none items-center justify-center gap-[6px] px-[40px] hairline-b">
          <h2 className="max-w-[70%] truncate text-pane font-medium tracking-[-0.012em]">
            {file.name}
          </h2>
          {menu !== undefined && menu.length > 0 && <MoreMenu items={menu} label={menuLabel} />}
        </div>
      )}
      <div
        data-viewer-bar="full"
        role="toolbar"
        aria-label="Viewer"
        className="flex h-[44px] flex-none items-center justify-center gap-[7px] hairline-b"
      >
        {zoomCapsule}
        <span className={CAPSULE}>
          <Tool
            icon="chevron-up"
            label="Previous page"
            disabled={at <= 1}
            onClick={() => {
              goTo(at - 1);
            }}
          />
          {pageCount}
          <Tool
            icon="chevron-down"
            label="Next page"
            disabled={at >= total}
            onClick={() => {
              goTo(at + 1);
            }}
          />
        </span>
        <span className={CAPSULE}>
          <Tool label="Highlight colour">
            <span
              aria-hidden="true"
              className="size-[15px] rounded-full bg-hl-rose inset-shadow-hair"
            />
            <Icon name="chevron-down" size={12} className="text-ink-3" />
          </Tool>
        </span>
        <span className={CAPSULE}>
          {finding ? (
            <span className="flex items-center gap-[4px] pr-[6px] pl-[6px]">
              <Icon name="search" size={13} className="text-ink-3" />
              <input
                aria-label="Find in document"
                placeholder="Find in document"
                value={query}
                ref={(el) => {
                  el?.focus();
                }}
                onChange={(e) => {
                  setQuery(e.target.value);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") find();
                  if (e.key === "Escape") {
                    e.stopPropagation();
                    setFinding(false);
                  }
                }}
                className="h-[26px] w-[150px] bg-transparent text-body outline-none placeholder:text-ink-3"
              />
            </span>
          ) : (
            <Tool
              icon="search"
              label="Find in document"
              onClick={() => {
                setFinding(true);
              }}
            />
          )}
        </span>
      </div>
    </>
  );

  return (
    <section
      data-viewer={variant}
      aria-label={file.name}
      style={height === undefined ? undefined : { height }}
      className={cn(
        "flex min-h-0 flex-col overflow-hidden bg-card",
        height === undefined && "h-full",
        className,
      )}
    >
      {bar}
      {aboveWell}
      {!ready && !loading ? (
        <StatusPane status={status} />
      ) : (
        <div
          ref={well}
          data-viewer-well=""
          // The pages scroll here and may hold no control: the well itself takes keyboard focus so
          // arrow keys scroll it (axe scrollable-region-focusable).
          role="region"
          aria-label={`Pages of ${file.name}`}
          tabIndex={0}
          {...(loading ? { "aria-busy": true } : {})}
          className={cn(
            "flex min-h-0 flex-1 flex-col items-center gap-[10px] overflow-auto bg-shell",
            evidence ? "px-[12px] pt-[12px]" : "py-[10px]",
          )}
        >
          {loading
            ? Array.from({ length: skeletons }, (_, i) => i).map((i) => (
                <Skeleton
                  key={i}
                  immediate
                  style={{ width: widthPx, height: Math.round(widthPx * 1.294) }}
                  className="flex-none rounded-none"
                />
              ))
            : file.pages.map((p) => (
                <Page
                  key={p.n}
                  page={p}
                  total={total}
                  file={file}
                  widthPx={widthPx}
                  zoom={zoom}
                  rotation={rotation}
                  reveal={reveal}
                  outline={outlineCited}
                  stack={stack}
                />
              ))}
          {!loading && afterPages}
        </div>
      )}
    </section>
  );
}

// ---- ReviewTree and FileChip ----------------------------------------------------------------------

export interface ReviewLeaf {
  label: string;
  match: MatchId;
}

export interface ReviewDoc {
  id: string;
  name: string;
  /** The check micro-pill: an ink check with this count, or a bare check when 0. Never green. */
  checks?: number;
  leaves?: readonly ReviewLeaf[];
}

export interface ReviewGroup {
  label: string;
  docs: readonly ReviewDoc[];
}

function Leaf({ leaf }: { leaf: ReviewLeaf }): JSX.Element {
  const { bind, pin } = useMatch(leaf.match, "row");
  return (
    <li>
      <button
        type="button"
        {...bind}
        onClick={(e) => {
          pin(e.currentTarget);
        }}
        className="flex h-[28px] w-full items-center pr-[10px] pl-[36px] text-left text-dense transition-[background-color] duration-[360ms] hover:bg-nav-fill data-[lit]:bg-match-bg"
      >
        {leaf.label}
      </button>
    </li>
  );
}

function Doc({ doc }: { doc: ReviewDoc }): JSX.Element {
  const [open, setOpen] = useState((doc.leaves ?? []).length > 0);
  const leaves = doc.leaves ?? [];
  return (
    <li>
      <button
        type="button"
        aria-expanded={leaves.length > 0 ? open : undefined}
        onClick={() => {
          setOpen((o) => !o);
        }}
        className="flex h-[32px] w-full items-center gap-[6px] px-[10px] text-left text-body hover:bg-nav-fill"
      >
        <Icon
          name={open && leaves.length > 0 ? "chevron-down" : "chevron-right"}
          size={12}
          className="shrink-0 text-ink-3"
        />
        <Icon name="file-text" size={13} className="shrink-0 text-ink-3" />
        <span className="min-w-0 flex-1 truncate">{doc.name}</span>
        {doc.checks !== undefined && (
          <span
            data-checks={doc.checks}
            className="inline-flex h-[18px] min-w-[21px] shrink-0 items-center justify-center gap-[3px] rounded-pill bg-card px-[5px] text-micro text-ink-3 shadow-e1"
          >
            <Icon
              name="check"
              size={12}
              label={`${String(doc.checks)} approved`}
              className="text-ink"
            />
            {doc.checks > 0 && <span className="text-ink-2">{doc.checks}</span>}
          </span>
        )}
      </button>
      {open && leaves.length > 0 && (
        <ul>
          {leaves.map((l) => (
            <Leaf key={l.label} leaf={l} />
          ))}
        </ul>
      )}
    </li>
  );
}

/** The ReviewTree (C-08, 214 wide): group heads, document rows with their check micro-pill, and
 * leaf rows that light with their match. */
export function ReviewTree({
  groups,
  label = "Review",
}: {
  groups: readonly ReviewGroup[];
  label?: string;
}): JSX.Element {
  return (
    <nav aria-label={label} className="flex flex-col pb-[8px]">
      {groups.map((g) => (
        <div key={g.label} className="flex flex-col">
          <h3 className="px-[12px] pt-[14px] pb-[6px] text-outline-hd text-ink-3 uppercase">
            {g.label}
          </h3>
          <ul>
            {g.docs.map((d) => (
              <Doc key={d.id} doc={d} />
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

/** A file reference in an issue (C-08 FileChip): lights while any region of its file is lit. */
export function FileChip({
  name,
  location,
  matches,
}: {
  name: string;
  location?: string;
  matches: readonly MatchId[];
}): JSX.Element {
  const { id } = useMatchState();
  const lit = id !== null && matches.includes(id);
  return (
    <span
      data-file-chip=""
      {...(lit ? { "data-lit": "" } : {})}
      className={cn(
        "inline-flex h-[28px] max-w-full items-center gap-[6px] rounded-pill bg-card pr-[12px] pl-[10px] text-cell shadow-e1 transition-[background-color,box-shadow] duration-[360ms]",
        lit && "bg-match-bg inset-ring-1 inset-ring-match-line",
      )}
    >
      <Icon name="file-text" size={12} className="shrink-0 text-ink-3" />
      <span className="min-w-0 truncate font-medium">{name}</span>
      {location !== undefined && <span className="shrink-0 text-ink-3">{location}</span>}
    </span>
  );
}
