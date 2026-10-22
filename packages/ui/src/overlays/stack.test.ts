// F-05-T20: the OverlayStack store on its own: push and pop order, the one-drawer rule, dirty flags,
// the subscription, and the focus-return helpers. The layers that use it are in overlays.test.tsx.
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  type LayerInit,
  type OverlayKind,
  captureOpener,
  createOverlayStack,
  restoreFocus,
  trackFocus,
} from "./stack";

const layer = (id: string, kind: OverlayKind, extra: Partial<LayerInit> = {}): LayerInit => ({
  id,
  kind,
  modal: kind !== "popover" && kind !== "peek",
  onRequestClose: () => undefined,
  ...extra,
});

afterEach(() => {
  document.body.replaceChildren();
});

describe("push and pop", () => {
  it("keeps layers in the order they opened, bottom first", () => {
    const stack = createOverlayStack();
    stack.push(layer("drawer", "drawer"));
    stack.push(layer("dialog", "dialog"));
    stack.push(layer("popover", "popover"));
    expect(stack.layers().map((l) => l.id)).toEqual(["drawer", "dialog", "popover"]);
    expect(stack.top()?.id).toBe("popover");
    expect(stack.indexOf("dialog")).toBe(1);
    expect(stack.indexOf("missing")).toBe(-1);
  });

  it("pops from the top and from the middle, and says what it removed", () => {
    const stack = createOverlayStack();
    stack.push(layer("a", "drawer"));
    stack.push(layer("b", "dialog"));
    stack.push(layer("c", "confirm"));
    expect(stack.pop("c")?.id).toBe("c");
    expect(stack.top()?.id).toBe("b");
    stack.push(layer("c", "confirm"));
    expect(stack.pop("b")?.id).toBe("b");
    expect(stack.layers().map((l) => l.id)).toEqual(["a", "c"]);
    expect(stack.pop("nope")).toBeUndefined();
  });

  it("is the topmost layer that isTop names, and only that one", () => {
    const stack = createOverlayStack();
    stack.push(layer("a", "drawer"));
    stack.push(layer("b", "dialog"));
    expect(stack.isTop("b")).toBe(true);
    expect(stack.isTop("a")).toBe(false);
    stack.pop("b");
    expect(stack.isTop("a")).toBe(true);
  });

  it("pushing an id that is open replaces its entry instead of doubling it", () => {
    const stack = createOverlayStack();
    stack.push(layer("a", "dialog"));
    stack.push(layer("a", "dialog", { dirty: true }));
    expect(stack.layers()).toHaveLength(1);
    expect(stack.layers()[0]?.dirty).toBe(true);
  });

  it("counts the modal layers: a popover and a peek do not hold the page", () => {
    const stack = createOverlayStack();
    stack.push(layer("peek", "peek"));
    stack.push(layer("pop", "popover"));
    expect(stack.modalCount()).toBe(0);
    stack.push(layer("dlg", "dialog"));
    stack.push(layer("drw", "sheet"));
    expect(stack.modalCount()).toBe(2);
  });
});

describe("one drawer at a time", () => {
  it("asks the open drawer to close, as replaced, when a second one opens", () => {
    const stack = createOverlayStack();
    const first = vi.fn();
    stack.push(layer("one", "drawer", { onRequestClose: first }));
    stack.push(layer("two", "drawer"));
    expect(first).toHaveBeenCalledExactlyOnceWith("replaced");
  });

  it("treats a peek as a drawer, in both orders", () => {
    const stack = createOverlayStack();
    const peek = vi.fn();
    stack.push(layer("peek", "peek", { onRequestClose: peek }));
    stack.push(layer("drawer", "drawer"));
    expect(peek).toHaveBeenCalledWith("replaced");
    const drawer = vi.fn();
    stack.pop("peek");
    stack.pop("drawer");
    stack.push(layer("drawer", "drawer", { onRequestClose: drawer }));
    stack.push(layer("peek", "peek"));
    expect(drawer).toHaveBeenCalledWith("replaced");
  });

  it("leaves a dialog, a sheet and a popover over a drawer alone", () => {
    const stack = createOverlayStack();
    const drawer = vi.fn();
    stack.push(layer("drawer", "drawer", { onRequestClose: drawer }));
    for (const kind of ["dialog", "sheet", "full-sheet", "popover", "confirm"] as const) {
      stack.push(layer(kind, kind));
    }
    expect(drawer).not.toHaveBeenCalled();
  });

  it("is left with the new drawer once the old one has closed itself", () => {
    const stack = createOverlayStack();
    stack.push(layer("one", "drawer", { onRequestClose: () => stack.pop("one") }));
    stack.push(layer("two", "drawer"));
    expect(stack.layers().map((l) => l.id)).toEqual(["two"]);
  });
});

describe("dirty and the subscription", () => {
  it("marks a layer dirty and clean, and tells subscribers only when it changed", () => {
    const stack = createOverlayStack();
    stack.push(layer("a", "dialog"));
    const listener = vi.fn();
    stack.subscribe(listener);
    stack.setDirty("a", true);
    expect(stack.layers()[0]?.dirty).toBe(true);
    stack.setDirty("a", true);
    expect(listener).toHaveBeenCalledTimes(1);
    stack.setDirty("a", false);
    expect(stack.layers()[0]?.dirty).toBe(false);
    stack.setDirty("missing", true);
    expect(listener).toHaveBeenCalledTimes(2);
  });

  it("hands out the same array until the stack changes, and stops after unsubscribe", () => {
    const stack = createOverlayStack();
    stack.push(layer("a", "dialog"));
    const before = stack.layers();
    expect(stack.layers()).toBe(before);
    const listener = vi.fn();
    const off = stack.subscribe(listener);
    stack.push(layer("b", "dialog"));
    expect(stack.layers()).not.toBe(before);
    off();
    stack.pop("b");
    expect(listener).toHaveBeenCalledTimes(1);
  });
});

describe("focus return", () => {
  it("captures the focused element and gives focus back to it", () => {
    const button = document.createElement("button");
    document.body.append(button);
    button.focus();
    const opener = captureOpener();
    expect(opener).toBe(button);
    const other = document.createElement("input");
    document.body.append(other);
    other.focus();
    expect(restoreFocus(opener)).toBe(true);
    expect(document.activeElement).toBe(button);
  });

  it("falls back to what was last pressed when nothing is focused, and skips what is gone", () => {
    trackFocus();
    const a = document.createElement("button");
    const b = document.createElement("button");
    document.body.append(a, b);
    a.focus();
    b.focus();
    b.blur();
    expect(document.activeElement).toBe(document.body);
    expect(captureOpener()).toBe(b);
    b.remove();
    expect(captureOpener()).toBe(a);
  });

  it("returns false, and moves nothing, when the opener left the page", () => {
    const gone = document.createElement("button");
    expect(restoreFocus(gone)).toBe(false);
    expect(restoreFocus(null)).toBe(false);
  });
});
