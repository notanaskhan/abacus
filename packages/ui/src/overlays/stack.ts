// OverlayStack (E3, plan 04 section 4.5; F-05-T20): the one place that knows which layers are open
// and in what order. A small external store, read through useSyncExternalStore (stack-react.tsx),
// with no Zustand and no Redux. Radix is the behaviour of each layer (focus trap, inert page,
// Escape, scroll lock); the stack is what makes them agree: Escape and outside presses reach only
// the topmost layer, a second drawer replaces the first, focus returns to whatever opened a layer,
// and a dirty layer is asked about before it closes.
//
// The store never decides what a layer looks like and never writes anything of its own: a layer
// is `{ id, kind, modal, dirty, onRequestClose }` and the store calls `onRequestClose` when a
// newer layer replaces it.

/** The layers of the O1 to O6 grammar, plus the confirm that sits over any of them. */
export type OverlayKind =
  | "popover" // O1 anchored card or tray
  | "drawer" // O2, modal
  | "peek" // O2, non-modal: no scrim, no trap
  | "sheet" // O3
  | "full-sheet" // O4
  | "palette" // O5
  | "wizard" // O6
  | "dialog" // C-22 Dialog
  | "confirm"; // C-22 ConfirmDialog, including "Discard changes?"

/** Why a layer is being asked to close. `replaced` skips the dirty guard; the others do not. */
export type CloseReason = "escape" | "outside" | "close" | "replaced";

export interface OverlayLayer {
  readonly id: string;
  readonly kind: OverlayKind;
  /** Modal layers trap focus and lock the page; a peek and an anchored card do not. */
  readonly modal: boolean;
  /** An unsaved form: closing asks "Discard changes?" first. */
  readonly dirty: boolean;
  /** What had focus when the layer opened; focus goes back to it when the layer closes. */
  readonly opener: HTMLElement | null;
  /** Close the layer: the owner sets its `open` to false. */
  readonly onRequestClose: (reason: CloseReason) => void;
}

export interface LayerInit {
  id: string;
  kind: OverlayKind;
  modal: boolean;
  dirty?: boolean;
  opener?: HTMLElement | null;
  onRequestClose: (reason: CloseReason) => void;
}

/** Only one drawer is ever open: a drawer, modal or peek, replaces the one before it (C-23). */
const isDrawer = (kind: OverlayKind): boolean => kind === "drawer" || kind === "peek";

export interface OverlayStack {
  /** Open a layer on top. A second drawer asks the first to close (`replaced`). Pushing an id that
   * is already open replaces its entry in place, so a re-run effect cannot double a layer. */
  push: (init: LayerInit) => void;
  /** Remove a layer, wherever it is in the stack, and return it. */
  pop: (id: string) => OverlayLayer | undefined;
  /** Mark a layer's form dirty or clean. */
  setDirty: (id: string, dirty: boolean) => void;
  /** Layers, bottom first. A new array only when the stack changes. */
  layers: () => readonly OverlayLayer[];
  top: () => OverlayLayer | undefined;
  /** True for the topmost layer only: the one Escape and outside presses belong to. */
  isTop: (id: string) => boolean;
  /** Position from the bottom, or -1. */
  indexOf: (id: string) => number;
  /** How many layers hold the page: the modal ones. */
  modalCount: () => number;
  subscribe: (listener: () => void) => () => void;
}

export function createOverlayStack(): OverlayStack {
  let layers: readonly OverlayLayer[] = [];
  const listeners = new Set<() => void>();

  const set = (next: readonly OverlayLayer[]): void => {
    layers = next;
    for (const listener of [...listeners]) listener();
  };

  return {
    push(init) {
      const layer: OverlayLayer = {
        id: init.id,
        kind: init.kind,
        modal: init.modal,
        dirty: init.dirty ?? false,
        opener: init.opener ?? null,
        onRequestClose: init.onRequestClose,
      };
      const existing = layers.findIndex((l) => l.id === layer.id);
      if (existing >= 0) {
        set(layers.map((l, i) => (i === existing ? layer : l)));
        return;
      }
      const replaced = isDrawer(layer.kind) ? layers.filter((l) => isDrawer(l.kind)) : [];
      set([...layers, layer]);
      // The older drawer is told once the new one is in; it closes itself (its owner sets `open` to
      // false, which pops it), so the new drawer is never the one that goes.
      for (const old of replaced) old.onRequestClose("replaced");
    },
    pop(id) {
      const found = layers.find((l) => l.id === id);
      if (found === undefined) return undefined;
      set(layers.filter((l) => l.id !== id));
      return found;
    },
    setDirty(id, dirty) {
      const found = layers.find((l) => l.id === id);
      if (found === undefined || found.dirty === dirty) return;
      set(layers.map((l) => (l.id === id ? { ...l, dirty } : l)));
    },
    layers: () => layers,
    top: () => layers[layers.length - 1],
    isTop: (id) => layers[layers.length - 1]?.id === id,
    indexOf: (id) => layers.findIndex((l) => l.id === id),
    modalCount: () => layers.filter((l) => l.modal).length,
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
}

// ---- Focus return ------------------------------------------------------------------------------

// Radix returns focus only to a Dialog.Trigger, and the app's dialogs open from their own buttons
// or from a menu item that is gone by then. So the stack remembers what the person last focused or
// pressed and hands it back. Safari does not focus a button on click, hence the pointer listener.
const RECENT_MAX = 8;
const recent: HTMLElement[] = [];
let tracking = false;

const FOCUSABLE = "button, a[href], input, select, textarea, [role='button'], [tabindex]";

function remember(el: Element | null): void {
  if (!(el instanceof HTMLElement) || el === document.body) return;
  recent.unshift(el);
  if (recent.length > RECENT_MAX) recent.length = RECENT_MAX;
}

/** Start remembering focus and presses. Safe to call again; a no-op where there is no document. */
export function trackFocus(): void {
  if (tracking || typeof document === "undefined") return;
  tracking = true;
  document.addEventListener("focusin", (e) => {
    remember(e.target instanceof Element ? e.target : null);
  });
  document.addEventListener(
    "pointerdown",
    (e) => {
      if (e.target instanceof Element) remember(e.target.closest(FOCUSABLE));
    },
    true,
  );
}

/** What should get focus back when a layer that is opening now closes. */
export function captureOpener(): HTMLElement | null {
  if (typeof document === "undefined") return null;
  const active = document.activeElement;
  if (active instanceof HTMLElement && active !== document.body && active.isConnected) {
    return active;
  }
  return recent.find((el) => el.isConnected) ?? null;
}

/** Give focus back to a layer's opener, if it is still on the page. Returns whether it did. */
export function restoreFocus(opener: HTMLElement | null): boolean {
  if (opener === null || !opener.isConnected) return false;
  opener.focus({ preventScroll: true });
  return document.activeElement === opener;
}

/** The app-wide stack. A provider (stack-react.tsx) can scope another one to a page or a test. */
export const appOverlayStack: OverlayStack = createOverlayStack();
