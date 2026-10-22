import {
  Children,
  type JSX,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { cn } from "../cn";
import { Drawer } from "../overlays/drawer";
import {
  SPLIT,
  SPLIT_PRESETS,
  type SplitPreset,
  type SplitPresetName,
  clampWidth,
  dragTarget,
  splitStorageKey,
} from "./split-presets";

// SplitLayout (F-05-T29; plan 04 §3.11; C-09): floating panes on the shell with 10px gutters, one
// row that never scrolls; each child brings its own Pane. Gutters resize (drag, ←/→ in 16px
// steps, Enter or a double click resets) within 280px and 60% of the row, and the widths persist
// per preset in localStorage behind try/catch. At 1280 or less the third column of `audit`,
// `audit-chat`, `taxReview` and `issues-individual` becomes a right drawer.

type Overrides = Record<number, number>;

function readSaved(preset: SplitPresetName): Overrides {
  try {
    const raw = window.localStorage.getItem(splitStorageKey(preset));
    if (raw === null) return {};
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return {};
    const out: Overrides = {};
    for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
      if (/^\d+$/.test(k) && typeof v === "number" && Number.isFinite(v)) out[Number(k)] = v;
    }
    return out;
  } catch {
    return {};
  }
}

function writeSaved(preset: SplitPresetName, overrides: Overrides): void {
  try {
    if (Object.keys(overrides).length === 0) {
      window.localStorage.removeItem(splitStorageKey(preset));
    } else {
      window.localStorage.setItem(splitStorageKey(preset), JSON.stringify(overrides));
    }
  } catch {
    // Storage refused (private mode, quota): the layout still works for this visit.
  }
}

const NARROW_QUERY = `(max-width: ${String(SPLIT.narrowAt)}px)`;

function subscribeNarrow(listener: () => void): () => void {
  if (typeof window.matchMedia !== "function") return () => undefined;
  const query = window.matchMedia(NARROW_QUERY);
  query.addEventListener("change", listener);
  return () => {
    query.removeEventListener("change", listener);
  };
}

/** The firm app's narrow layout: a window 1280 wide or less. */
export function useNarrowLayout(): boolean {
  return useSyncExternalStore(
    subscribeNarrow,
    () => typeof window.matchMedia === "function" && window.matchMedia(NARROW_QUERY).matches,
    () => false,
  );
}

export interface SplitLayoutProps {
  preset: SplitPresetName;
  /** The panes, in order; each is a `Pane`. */
  children: ReactNode;
  /** px, or `viewport`: the window less the toolbar (46) and `headerRows`. */
  height?: number | "viewport";
  /** The rows above the layout (record header and tabs); default 92. */
  headerRows?: number;
  /** Force (true) or forbid (false) the narrow drawer mode; default: the window is ≤ 1280. */
  narrow?: boolean;
  /** Narrow mode: the drawer holding the third column (the tabsbar ViewToggle drives it). */
  drawerOpen?: boolean;
  onDrawerOpenChange?: (open: boolean) => void;
  /** The drawer's title: the third pane's name. */
  drawerTitle?: string;
  className?: string;
}

export function SplitLayout({
  preset,
  children,
  height = "viewport",
  headerRows = 92,
  narrow,
  drawerOpen = false,
  onDrawerOpenChange,
  drawerTitle = "Details",
  className,
}: SplitLayoutProps): JSX.Element {
  const spec: SplitPreset = SPLIT_PRESETS[preset];
  const panes = spec.panes;
  const resizable = spec.resizable !== false;
  const hasDrawer = spec.drawer === true;
  const windowNarrow = useNarrowLayout();
  const drawerMode = hasDrawer && (narrow ?? windowNarrow);
  const row = useRef<HTMLDivElement>(null);
  const [rowInner, setRowInner] = useState(0);
  const [overrides, setOverrides] = useState<Overrides>({});

  // Saved widths load after mount (storage is the browser's) and are re-clamped to the row.
  useEffect(() => {
    setOverrides(readSaved(preset));
  }, [preset]);

  useLayoutEffect(() => {
    const el = row.current;
    if (el === null || typeof ResizeObserver !== "function") return;
    const observer = new ResizeObserver(([entry]) => {
      setRowInner(entry?.contentRect.width ?? 0);
    });
    observer.observe(el);
    return () => {
      observer.disconnect();
    };
  }, []);

  const commit = useCallback(
    (next: Overrides) => {
      setOverrides(next);
      writeSaved(preset, next);
    },
    [preset],
  );

  const shown = drawerMode ? panes.slice(0, 2) : panes;
  const items = Children.toArray(children);
  const rowHeight =
    height === "viewport" ? `calc(100vh - 46px - ${String(headerRows)}px)` : `${String(height)}px`;

  function widthOf(i: number): number | undefined {
    const saved = overrides[i];
    const design = shown[i];
    if (design === undefined) return undefined;
    if (saved !== undefined) return clampWidth(saved, rowInner, shown, overrides, i);
    return design.flex === true ? undefined : design.width;
  }

  return (
    <>
      <div
        ref={row}
        data-split={preset}
        data-narrow={drawerMode ? "true" : undefined}
        style={{ height: rowHeight }}
        className={cn("flex min-h-0 bg-shell pt-[10px] pr-[12px] pb-[12px] pl-[12px]", className)}
      >
        {shown.map((pane, i) => {
          const w = widthOf(i);
          const flexing = w === undefined;
          return (
            <PaneSlot
              key={i}
              index={i}
              width={w}
              basis={pane.width}
              min={
                pane.flex === true
                  ? (pane.min ?? SPLIT.minPane)
                  : Math.min(SPLIT.minPane, pane.width)
              }
              flexing={flexing}
              gutterAfter={i < shown.length - 1}
              resizable={resizable}
              onResize={(gutter, delta) => {
                const { target, sign } = dragTarget(gutter, shown, overrides);
                const from =
                  overrides[target] ??
                  measure(row.current, target) ??
                  shown[target]?.width ??
                  SPLIT.minPane;
                const next = { ...overrides };
                next[target] = clampWidth(from + sign * delta, rowInner, shown, overrides, target);
                commit(next);
              }}
              onReset={() => {
                commit({});
              }}
            >
              {items[i]}
            </PaneSlot>
          );
        })}
      </div>
      {drawerMode && items[2] !== undefined && (
        <Drawer
          open={drawerOpen}
          onOpenChange={(open) => onDrawerOpenChange?.(open)}
          title={drawerTitle}
          width={preset === "audit" ? 480 : 420}
          bare
        >
          {items[2]}
        </Drawer>
      )}
    </>
  );
}

function measure(rowEl: HTMLDivElement | null, index: number): number | undefined {
  const slot = rowEl?.querySelector<HTMLElement>(`[data-split-pane="${String(index)}"]`);
  const w = slot?.getBoundingClientRect().width;
  return w === undefined || w === 0 ? undefined : Math.round(w);
}

interface PaneSlotProps {
  index: number;
  width: number | undefined;
  basis: number;
  min: number;
  flexing: boolean;
  gutterAfter: boolean;
  resizable: boolean;
  onResize: (gutter: number, delta: number) => void;
  onReset: () => void;
  children: ReactNode;
}

function PaneSlot({
  index,
  width,
  basis,
  min,
  flexing,
  gutterAfter,
  resizable,
  onResize,
  onReset,
  children,
}: PaneSlotProps): JSX.Element {
  return (
    <>
      <div
        data-split-pane={index}
        style={
          flexing
            ? { flex: `1 1 ${String(basis)}px`, minWidth: min }
            : { flex: "0 1 auto", width, minWidth: min }
        }
        className="flex min-h-0 flex-col [&>*]:min-h-0 [&>*]:flex-1"
      >
        {children}
      </div>
      {gutterAfter &&
        (resizable ? (
          <ResizeGutter
            index={index}
            width={width ?? basis}
            onResize={onResize}
            onReset={onReset}
          />
        ) : (
          <div aria-hidden="true" className="w-[10px] shrink-0" />
        ))}
    </>
  );
}

export interface ResizeGutterProps {
  /** The gutter after pane `index`. */
  index: number;
  /** The width of the pane it resizes, for `aria-valuenow`. */
  width?: number | undefined;
  onResize: (gutter: number, delta: number) => void;
  onReset: () => void;
}

/**
 * The 10px gutter between two panes (C-09): a focusable vertical separator with a 2×36 handle
 * that fades in on hover, drag or focus. ←/→ move it 16px; Enter or a double click resets.
 */
export function ResizeGutter({ index, width, onResize, onReset }: ResizeGutterProps): JSX.Element {
  const drag = useRef<{ x: number } | null>(null);
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      onResize(index, event.key === "ArrowRight" ? SPLIT.nudge : -SPLIT.nudge);
    } else if (event.key === "Enter") {
      event.preventDefault();
      onReset();
    }
  }
  function onPointerDown(event: PointerEvent<HTMLDivElement>): void {
    drag.current = { x: event.clientX };
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function onPointerMove(event: PointerEvent<HTMLDivElement>): void {
    if (drag.current === null) return;
    const delta = event.clientX - drag.current.x;
    if (delta === 0) return;
    drag.current = { x: event.clientX };
    onResize(index, delta);
  }
  function onPointerUp(event: PointerEvent<HTMLDivElement>): void {
    drag.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }
  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize panes"
      aria-valuenow={width}
      aria-valuemin={SPLIT.minPane}
      tabIndex={0}
      data-gutter={index}
      onKeyDown={onKeyDown}
      onDoubleClick={onReset}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      className="group relative flex w-[10px] shrink-0 cursor-col-resize touch-none items-center justify-center rounded-pill focus-visible:outline-offset-0"
    >
      <span
        aria-hidden="true"
        className="h-9 w-[2px] rounded-pill bg-stroke opacity-0 transition-opacity duration-160 group-hover:opacity-100 group-focus-visible:opacity-100 group-active:opacity-100"
      />
    </div>
  );
}

export interface NestedSplitProps {
  /** `hair`: columns split by a 0.5px rule (close-review). `well`: an 8px shell well of cards (issues-individual). */
  kind: "hair" | "well";
  /** Column widths in px; `flex` grows. Never more than two levels deep. */
  columns: readonly (number | "flex")[];
  children: ReactNode;
  className?: string;
}

/** Columns inside one pane (C-09 NestedSplit). */
export function NestedSplit({
  kind,
  columns,
  children,
  className,
}: NestedSplitProps): JSX.Element {
  const items = Children.toArray(children);
  return (
    <div
      data-nested={kind}
      className={cn(
        "flex min-h-0 flex-1",
        kind === "well" && "gap-[8px] bg-shell p-[8px]",
        className,
      )}
    >
      {columns.map((w, i) => (
        <div
          key={i}
          style={w === "flex" ? { flex: "1 1 0", minWidth: 0 } : { width: w, flex: "0 0 auto" }}
          className={cn(
            "flex min-h-0 flex-col overflow-auto",
            kind === "hair" && i < columns.length - 1 && "border-r-[0.5px] border-hair",
            kind === "well" && "rounded-nested bg-card shadow-e1",
          )}
        >
          {items[i]}
        </div>
      ))}
    </div>
  );
}
