import type { ContractMatch, Locator, MatchId, MatchKind } from "./types";

// E1 MatchStore (F-05-T41; plan 04 §4.3 E1, after the handoff's lib/match.js): one active match per
// scope, as an external store React reads through `useSyncExternalStore`. Nothing here touches the
// DOM's classes: an element is lit because its own hook reads `get().id === its id`, so a change
// re-renders the element that goes dark and the one that lights, and nothing else.
//
// Timing (lib/match.js, C-07):
//   intent   120ms for rows, cells and regions; 150ms for markers, before the match lights
//   release  140ms after the pointer leaves, unless pinned; 200ms for a marker and its popover
//   light    one 360ms transition on every element carrying the id (the CSS, `MATCH_LIGHT_MS`)
//   pin      a click pins (and a second click on the same match unpins); Escape clears and
//            returns focus to the element the match came from

export const INTENT_MS = 120;
export const MARKER_INTENT_MS = 150;
export const RELEASE_MS = 140;
export const MARKER_RELEASE_MS = 200;
export const MATCH_LIGHT_MS = 360;

/** The match id of a typed C4 locator, derived as the server derives it (C4 §3.1; INV-2). */
export function matchIdOf(locator: Locator): MatchId {
  return idOf(locator) as MatchId;
}

/** The server's `match_id` off a typed C4 citation or region (INV-2: never from model text). */
export function contractMatchId(source: ContractMatch): MatchId {
  return source.match_id as MatchId;
}

function idOf(locator: Locator): string {
  switch (locator.kind) {
    case "document_text": {
      const at = `ev:${locator.evidence_version_id}#p${String(locator.page)}`;
      return locator.bbox === undefined || locator.bbox === null
        ? at
        : `${at}:${locator.bbox.map(String).join(",")}`;
    }
    case "sheet_cell":
      return `${locator.file}!${locator.cell}`;
    case "ledger_line":
      return `led:${locator.ledger_snapshot_id}:${locator.account_code}`;
    case "workpaper_cell":
      return `wp:${locator.sheet_id}.${locator.row_key}.${locator.column_key}`;
    case "methodology_step":
      return `ms:${locator.step_key}@${locator.template_version_id}`;
    case "policy_rule":
      return `pol:${locator.threshold_policy_id}@v${String(locator.version)}`;
    case "record_field":
      return `rec:${locator.record_type}:${locator.record_id}.${locator.field}`;
    case "tax_form_line":
      return `tax:${locator.return_id}:${locator.form}:${locator.line}`;
    case "artifact_cell":
      return `art:${locator.run_artifact_id}!${locator.cell}`;
    case "request_item":
      return `req:${locator.request_item_id}`;
  }
}

export interface MatchState<P = unknown> {
  /** The lit match, or none. */
  id: MatchId | null;
  pinned: boolean;
  /** The element the match came from: anchors fall back to it, Escape refocuses it. */
  origin: HTMLElement | null;
  /** What the anchored popover shows for this match; null means no popover. */
  payload: P | null;
}

export interface MatchStore<P = unknown> {
  get: () => MatchState<P>;
  subscribe: (listener: () => void) => () => void;
  /** The pointer or focus is on `id`: light it after the kind's intent delay. */
  intent: (
    id: MatchId | null,
    origin: HTMLElement | null,
    kind?: MatchKind,
    payload?: P | null,
  ) => void;
  /** The pointer or focus left: go dark after the release delay, unless pinned. */
  release: (kind?: MatchKind) => void;
  /** Keep the current match lit (the pointer is over its popover). */
  hold: () => void;
  /** Light now, with no delay (a step, a menu row, a test). */
  light: (id: MatchId | null, origin?: HTMLElement | null, payload?: P | null) => void;
  /** A click: pin this match, or unpin it when it is the pinned one. */
  togglePin: (id: MatchId | null, origin: HTMLElement | null, payload?: P | null) => void;
  /** Move the lit match within a pinned or open payload (the popover's ‹ ›). */
  retarget: (id: MatchId | null, payload: P | null) => void;
  clear: () => void;
  /** Escape: clear, then return focus to where the match came from. */
  escape: () => void;
  /** The element to anchor to: the first carrying the id inside the origin's scope, then the page;
   * a range falls back to its first cell, then to its sheet; else the origin itself. */
  anchorFor: (id?: MatchId | null, origin?: HTMLElement | null) => HTMLElement | null;
}

const EMPTY: MatchState<never> = { id: null, pinned: false, origin: null, payload: null };

function intentFor(kind: MatchKind): number {
  return kind === "marker" ? MARKER_INTENT_MS : INTENT_MS;
}

function releaseFor(kind: MatchKind): number {
  return kind === "marker" ? MARKER_RELEASE_MS : RELEASE_MS;
}

/** `data-match` selector for an id, quoting what CSS needs quoted. */
function selector(id: string, prefix = false): string {
  const quoted = id.replace(/["\\]/g, "\\$&");
  return prefix ? `[data-match^="${quoted}"]` : `[data-match="${quoted}"]`;
}

/** Candidate ids for an anchor, best first: the id, a range's first cell, the range's sheet. */
function candidates(id: string): { id: string; prefix: boolean }[] {
  const out = [{ id, prefix: false }];
  const bang = id.lastIndexOf("!");
  if (bang < 0) return out;
  const range = id.slice(bang + 1);
  const colon = range.indexOf(":");
  if (colon > 0)
    out.push({ id: `${id.slice(0, bang + 1)}${range.slice(0, colon)}`, prefix: false });
  out.push({ id: id.slice(0, bang + 1), prefix: true });
  return out;
}

export function createMatchStore<P = unknown>(): MatchStore<P> {
  let state: MatchState<P> = EMPTY;
  const listeners = new Set<() => void>();
  let pending: ReturnType<typeof setTimeout> | null = null;
  let releasing: ReturnType<typeof setTimeout> | null = null;

  const emit = (next: MatchState<P>): void => {
    if (
      next.id === state.id &&
      next.pinned === state.pinned &&
      next.origin === state.origin &&
      next.payload === state.payload
    ) {
      return;
    }
    state = next;
    for (const listener of listeners) listener();
  };
  const cancelIntent = (): void => {
    if (pending !== null) clearTimeout(pending);
    pending = null;
  };
  const cancelRelease = (): void => {
    if (releasing !== null) clearTimeout(releasing);
    releasing = null;
  };
  const light = (
    id: MatchId | null,
    origin: HTMLElement | null = null,
    payload: P | null = null,
  ): void => {
    cancelIntent();
    cancelRelease();
    emit({ id, pinned: state.pinned && state.id === id, origin, payload });
  };
  const clear = (): void => {
    cancelIntent();
    cancelRelease();
    emit(EMPTY);
  };

  const anchorFor = (
    id: MatchId | null = state.id,
    origin: HTMLElement | null = state.origin,
  ): HTMLElement | null => {
    if (id === null || typeof document === "undefined") return origin;
    const scope = origin?.closest<HTMLElement>("[data-match-scope]") ?? null;
    const roots: ParentNode[] = scope === null ? [document] : [scope, document];
    for (const candidate of candidates(id)) {
      for (const root of roots) {
        const found = Array.from(
          root.querySelectorAll<HTMLElement>(selector(candidate.id, candidate.prefix)),
        ).find((el) => origin === null || !origin.contains(el));
        if (found !== undefined) return found;
      }
    }
    return origin;
  };

  return {
    get: () => state,
    subscribe: (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    intent: (id, origin, kind = "row", payload = null) => {
      cancelRelease();
      cancelIntent();
      if (state.pinned) return;
      if (state.id === id && state.origin === origin) return;
      pending = setTimeout(() => {
        pending = null;
        emit({ id, pinned: false, origin, payload });
      }, intentFor(kind));
    },
    release: (kind = "row") => {
      cancelIntent();
      if (state.pinned || (state.id === null && state.payload === null)) return;
      cancelRelease();
      releasing = setTimeout(() => {
        releasing = null;
        emit(EMPTY);
      }, releaseFor(kind));
    },
    hold: cancelRelease,
    light,
    togglePin: (id, origin, payload = null) => {
      cancelIntent();
      cancelRelease();
      if (state.pinned && state.id === id && state.origin === origin) {
        emit(EMPTY);
        return;
      }
      emit({ id, pinned: true, origin, payload });
    },
    retarget: (id, payload) => {
      cancelIntent();
      cancelRelease();
      emit({ ...state, id, payload });
    },
    clear,
    escape: () => {
      const origin = state.origin;
      if (state.id === null && state.payload === null) return;
      clear();
      origin?.focus();
    },
    anchorFor,
  };
}
