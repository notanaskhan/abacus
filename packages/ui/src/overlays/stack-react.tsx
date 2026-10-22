import {
  type JSX,
  type ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import {
  type CloseReason,
  type OverlayKind,
  type OverlayLayer,
  type OverlayStack,
  appOverlayStack,
  captureOpener,
  createOverlayStack,
  restoreFocus,
  trackFocus,
} from "./stack";

// The React side of the OverlayStack: a provider that scopes a stack to a page (or a test), the
// hooks that read it, and `useOverlayLayer`, which every layer of the O1 to O6 grammar uses to
// join the stack while it is open.

const StackContext = createContext<OverlayStack>(appOverlayStack);

/** Give a subtree its own stack. Without one, every layer joins the app-wide stack. */
export function OverlayStackProvider({
  stack,
  children,
}: {
  stack?: OverlayStack;
  children: ReactNode;
}): JSX.Element {
  const [own] = useState(() => stack ?? createOverlayStack());
  return <StackContext.Provider value={own}>{children}</StackContext.Provider>;
}

export function useOverlayStack(): OverlayStack {
  return useContext(StackContext);
}

/** The layers, bottom first, re-read whenever the stack changes. */
export function useOverlayLayers(): readonly OverlayLayer[] {
  const stack = useOverlayStack();
  return useSyncExternalStore(stack.subscribe, stack.layers, stack.layers);
}

// ---- Z-order -----------------------------------------------------------------------------------

// Layers stack in the order they opened: each one takes two steps above the one under it (its
// scrim, then its panel), starting at the drawer level (`--z-drawer`, root.css). The toast sits at
// `--z-toast`, above ten layers.
const STEP = 2;

/** The z-index of the scrim of the layer at `index`; its panel is one above. */
export function layerZ(index: number): string {
  return `calc(var(--z-drawer) + ${String(index * STEP)})`;
}

/** The z-index of a panel at `index`. */
export function panelZ(index: number): string {
  return `calc(var(--z-drawer) + ${String(index * STEP + 1)})`;
}

/** The z-index for a floating layer that is not itself in the stack (a menu, a tooltip): above
 * everything that is. Re-read when the stack changes, so a menu opened inside a dialog stays on top. */
export function useAnchoredZ(): string {
  const layers = useOverlayLayers();
  return panelZ(layers.length);
}

// ---- A layer -----------------------------------------------------------------------------------

export interface LayerOptions {
  kind: OverlayKind;
  modal: boolean;
  open: boolean;
  /** Unsaved changes: Escape, the close button and the scrim ask "Discard changes?" first. */
  dirty?: boolean;
  onOpenChange: (open: boolean) => void;
}

export interface LayerHandle {
  id: string;
  /** Where this layer sits from the bottom, or what it will be once it opens. */
  index: number;
  scrimZ: string;
  panelZ: string;
  /** Ask the layer to close: through the guard when it is dirty. */
  requestClose: (reason: CloseReason) => void;
  /** For Radix's `onOpenChange`: opening passes through, closing is a request. */
  onRootOpenChange: (open: boolean) => void;
  /** For Radix's `onPointerDownOutside`: only the topmost layer dismisses. */
  onlyTop: (event: { preventDefault: () => void }) => void;
  /** For Radix's `onEscapeKeyDown`: the stack decides, not Radix. Whichever layer hears the
   * keydown cancels Radix's own dismissal and asks the topmost layer of the stack to close, once.
   * Radix gives the key to the highest layer of its own count, which can lag a layer that has just
   * opened, and counts separately per package version; the stack is the one order that is right. */
  onEscape: (event: Pick<KeyboardEvent, "preventDefault" | "defaultPrevented">) => void;
  /** For Radix's `onCloseAutoFocus`: focus goes back to what opened the layer. With `onlyIfLost`
   * (a peek) only when focus has nowhere else to be: the person may have moved on. */
  returnFocus: (event: { preventDefault: () => void }, onlyIfLost?: boolean) => void;
  /** The dirty guard is showing over this layer. */
  guarding: boolean;
  /** Discard: close the layer without asking again. */
  discard: () => void;
  /** Keep editing: dismiss the guard. */
  keepEditing: () => void;
}

export function useOverlayLayer({
  kind,
  modal,
  open,
  dirty,
  onOpenChange,
}: LayerOptions): LayerHandle {
  const stack = useOverlayStack();
  const id = useId();
  const layers = useOverlayLayers();
  const [guarding, setGuarding] = useState(false);
  const opener = useRef<HTMLElement | null>(null);
  const latest = useRef({ dirty: dirty ?? false, onOpenChange });
  latest.current = { dirty: dirty ?? false, onOpenChange };

  const requestClose = useCallback((reason: CloseReason): void => {
    if (reason === "replaced" || !latest.current.dirty) {
      latest.current.onOpenChange(false);
      return;
    }
    setGuarding(true);
  }, []);

  // A layer that closed has no guard to keep.
  if (!open && guarding) setGuarding(false);

  useEffect(() => {
    trackFocus();
  }, []);

  // Join the stack for as long as the layer is open. The opener is read here, before Radix moves
  // focus into the layer.
  useLayoutEffect(() => {
    if (!open) return;
    opener.current = captureOpener();
    stack.push({
      id,
      kind,
      modal,
      dirty: latest.current.dirty,
      opener: opener.current,
      onRequestClose: requestClose,
    });
    return () => {
      stack.pop(id);
    };
  }, [open, stack, id, kind, modal, requestClose]);

  useEffect(() => {
    if (open) stack.setDirty(id, dirty ?? false);
  }, [open, dirty, stack, id]);

  const found = layers.findIndex((l) => l.id === id);
  const index = found >= 0 ? found : layers.length;

  const onlyTop = useCallback(
    (event: { preventDefault: () => void }): void => {
      const top = stack.top();
      if (top !== undefined && top.id !== id) event.preventDefault();
    },
    [stack, id],
  );

  const onEscape = useCallback(
    (event: Pick<KeyboardEvent, "preventDefault" | "defaultPrevented">): void => {
      // The same keydown reaches every layer that thinks it is the highest: the first one handles it.
      if (event.defaultPrevented) return;
      event.preventDefault();
      stack.top()?.onRequestClose("escape");
    },
    [stack],
  );

  const returnFocus = useCallback(
    (event: { preventDefault: () => void }, onlyIfLost = false): void => {
      event.preventDefault();
      if (onlyIfLost) {
        const active = document.activeElement;
        if (active !== null && active !== document.body) return;
      }
      restoreFocus(opener.current);
    },
    [],
  );

  const onRootOpenChange = useCallback(
    (next: boolean): void => {
      if (next) latest.current.onOpenChange(true);
      else requestClose("close");
    },
    [requestClose],
  );

  return useMemo(
    () => ({
      id,
      index,
      scrimZ: layerZ(index),
      panelZ: panelZ(index),
      requestClose,
      onRootOpenChange,
      onlyTop,
      onEscape,
      returnFocus,
      guarding,
      discard: () => {
        setGuarding(false);
        latest.current.onOpenChange(false);
      },
      keepEditing: () => {
        setGuarding(false);
      },
    }),
    [id, index, requestClose, onRootOpenChange, onlyTop, onEscape, returnFocus, guarding],
  );
}
