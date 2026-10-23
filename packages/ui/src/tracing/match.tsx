import {
  type FocusEvent,
  type JSX,
  type PointerEvent,
  type ReactNode,
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react";
import { cn } from "../cn";
import { useOverlayStack } from "../overlays/stack-react";
import { type MatchState, type MatchStore, createMatchStore } from "./match-store";
import type { CitationPayload, MatchId, MatchKind } from "./types";

// E1 MatchProvider, the React side (F-05-T41): `MatchScope` gives a subtree one store (one active
// match per scope), `useMatch(id)` lights an element, and the classes below draw the light. Without
// a scope, elements share the page's store. Tracing attributes are public API (plan 04 §6 rule 4):
// what can be lit renders `data-match`, a scope renders `data-match-scope`.

/** The match store every tracing element on a page shares when no scope is closer. */
const pageStore = createMatchStore<CitationPayload>();
const StoreContext = createContext<MatchStore<CitationPayload>>(pageStore);

export function useMatchStore(): MatchStore<CitationPayload> {
  return useContext(StoreContext);
}

/** The whole state, for a host that draws the popover. Every change re-renders its reader. */
export function useMatchState(): MatchState<CitationPayload> {
  const store = useMatchStore();
  return useSyncExternalStore(store.subscribe, store.get, store.get);
}

export interface MatchScopeProps {
  /** A store to use (a test, a page that drives it); one is made otherwise. */
  store?: MatchStore<CitationPayload>;
  className?: string;
  children?: ReactNode;
}

/** One store, one active match, for the panes inside it (T3 wraps its three panes in one). Escape
 * clears the match and returns focus, unless an overlay layer is open (its Escape comes first). */
export function MatchScope({ store, className, children }: MatchScopeProps): JSX.Element {
  const [own] = useState(() => store ?? createMatchStore<CitationPayload>());
  const stack = useOverlayStack();
  useEffect(() => {
    const onKey = (event: KeyboardEvent): void => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      if (stack.layers().length > 0) return;
      const { id, payload } = own.get();
      if (id === null && payload === null) return;
      own.escape();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      own.clear();
    };
  }, [own, stack]);
  return (
    <StoreContext.Provider value={own}>
      <div data-match-scope="" className={cn("contents", className)}>
        {children}
      </div>
    </StoreContext.Provider>
  );
}

/** The props `useMatch` spreads on the element it lights. */
export interface MatchBind {
  "data-match": MatchId;
  "data-lit"?: "";
  onPointerEnter: (event: PointerEvent<HTMLElement>) => void;
  onPointerLeave: () => void;
  onFocus: (event: FocusEvent<HTMLElement>) => void;
  onBlur: () => void;
}

export interface UseMatch {
  /** This element's match is the scope's active one. */
  lit: boolean;
  /** Spread on the element: `data-match`, `data-lit` and the hover and focus intents. */
  bind: MatchBind;
  /** Pin or unpin this match (a click). */
  pin: (origin: HTMLElement | null) => void;
}

/**
 * Light an element with the scope's match. Re-renders only when this element's own lit state
 * changes (a boolean selector over the store), so moving the match re-renders two elements.
 */
export function useMatch(id: MatchId, kind: MatchKind = "row"): UseMatch {
  const store = useMatchStore();
  const lit = useSyncExternalStore(
    store.subscribe,
    () => store.get().id === id,
    () => false,
  );
  const handlers = useMemo(
    () => ({
      onPointerEnter: (event: PointerEvent<HTMLElement>) => {
        store.intent(id, event.currentTarget, kind);
      },
      onPointerLeave: () => {
        store.release(kind);
      },
      onFocus: (event: FocusEvent<HTMLElement>) => {
        store.intent(id, event.currentTarget, kind);
      },
      onBlur: () => {
        store.release(kind);
      },
      pin: (origin: HTMLElement | null) => {
        store.togglePin(id, origin);
      },
    }),
    [store, id, kind],
  );
  const { pin, ...events } = handlers;
  return {
    lit,
    bind: { "data-match": id, ...(lit ? { "data-lit": "" as const } : {}), ...events },
    pin,
  };
}

// ---- The light ----------------------------------------------------------------------------------

// One 360ms fade on every lit element (C-07 "What the active match lights"). Purple is tracing
// only: never a status. Reduced motion cuts the fade (motion.css), not the light.
const FADE = "transition-[background-color,box-shadow,color] duration-[360ms] ease-out";

/** A lit row: the match fill. */
export const MATCH_ROW = cn(FADE, "data-[lit]:bg-match-bg");

/** A lit exact cell: the deeper fill, a 1.5px inset line, match ink at 500. */
export const MATCH_CELL = cn(
  FADE,
  "data-[lit]:bg-match-bg-2 data-[lit]:font-medium data-[lit]:text-match-ink data-[lit]:inset-ring-[1.5px] data-[lit]:inset-ring-match-line",
);

/** A region on a page image: invisible until lit, then the soft match fill and its line. */
export const MATCH_REGION = cn(
  FADE,
  "data-[lit]:bg-match-soft data-[lit]:inset-ring-1 data-[lit]:inset-ring-match-line",
);

const LIGHT: Record<MatchKind, string> = {
  row: MATCH_ROW,
  cell: MATCH_CELL,
  region: MATCH_REGION,
  marker: MATCH_ROW,
};

export interface MatchableProps {
  id: MatchId;
  kind?: MatchKind;
  /** The element: a span by default (`td`, `tr` and `div` too). */
  as?: "span" | "div" | "td" | "tr" | "li";
  className?: string;
  children?: ReactNode;
}

/** An element that lights with its match: `data-match`, the hover and focus intents, the light. */
export function Matchable({
  id,
  kind = "row",
  as: Tag = "span",
  className,
  children,
}: MatchableProps): JSX.Element {
  const { bind } = useMatch(id, kind);
  return (
    <Tag {...bind} data-match-kind={kind} className={cn(LIGHT[kind], className)}>
      {children}
    </Tag>
  );
}
