import { type MockInstance, afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createToast, createToastStore } from "./toast-store";

// F-05-T22: independent acceptance tests (ADR-078) for E2 toasts and Undo, from F-05 §3.E:
// "the toast rises … dismisses after 4 s (8 s with an action), pauses on hover, and at most 3
// toasts are live"; "toast.undoable({text, onUndo, windowMs: 10_000}) … when Undo is clicked inside
// the window, then the toast calls only the module's compensating command … and Undo disappears
// once the module reports the effect has started. The toast store never issues a write of its own
// and never shows a human gate optimistically (INV-1)."

const fetchSpy = vi.fn();
let xhrOpen: MockInstance | undefined;

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "performance"] });
  fetchSpy.mockReset();
  vi.stubGlobal("fetch", fetchSpy);
  xhrOpen = vi.spyOn(XMLHttpRequest.prototype, "open");
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  xhrOpen?.mockRestore();
});

function noNetwork(): void {
  expect(fetchSpy).not.toHaveBeenCalled();
  expect(xhrOpen).not.toHaveBeenCalled();
}

const live = (s: ReturnType<typeof createToastStore>) => s.list().filter((t) => !t.leaving);

describe("E2 confirmations", () => {
  it("4 s, 8 s with an action, at most 3 live, hover pauses", () => {
    const store = createToastStore();
    const toast = createToast(store);
    toast.show("Firm settings saved");
    toast.show({ text: "Reply sent", action: "View" });
    vi.advanceTimersByTime(4000);
    expect(live(store).map((t) => t.text)).toEqual(["Reply sent"]);
    vi.advanceTimersByTime(4000);
    expect(live(store)).toHaveLength(0);

    for (const text of ["One", "Two", "Three", "Four"]) toast.show(text);
    expect(live(store).map((t) => t.text)).toEqual(["Two", "Three", "Four"]);

    const held = toast.show("Held");
    store.pause(held);
    vi.advanceTimersByTime(20_000);
    expect(live(store).some((t) => t.id === held)).toBe(true);
    noNetwork();
  });
});

describe("Undo (DEC-24) and INV-1", () => {
  it("Undo inside the window calls only the compensating command; the store writes nothing", () => {
    const toast = createToast(createToastStore());
    const onUndo = vi.fn();
    const handle = toast.undoable({ text: "Archived Northwind", undo: onUndo, windowMs: 10_000 });
    vi.advanceTimersByTime(9_999);
    toast.act(handle.id);
    expect(onUndo).toHaveBeenCalledOnce();
    vi.advanceTimersByTime(60_000);
    expect(onUndo).toHaveBeenCalledOnce();
    noNetwork();
  });

  it("after the window, Undo is gone and does nothing", () => {
    const store = createToastStore();
    const toast = createToast(store);
    const onUndo = vi.fn();
    const handle = toast.undoable({ text: "Archived Northwind", undo: onUndo, windowMs: 10_000 });
    vi.advanceTimersByTime(10_000);
    expect(live(store)).toHaveLength(0);
    toast.act(handle.id);
    expect(onUndo).not.toHaveBeenCalled();
    noNetwork();
  });

  it("Undo disappears once the module reports the effect has started", () => {
    const store = createToastStore();
    const toast = createToast(store);
    const onUndo = vi.fn();
    const handle = toast.undoable({ text: "Request sent", undo: onUndo });
    expect(store.list()[0]?.action).toBe("Undo");
    handle.started();
    expect(store.list()[0]?.action).toBeNull();
    toast.act(handle.id);
    expect(onUndo).not.toHaveBeenCalled();
  });

  it("a gate is never written early: the deferred commit waits out the window", () => {
    const toast = createToast(createToastStore());
    const commit = vi.fn();
    toast.undoable({ text: "Signed off as reviewer", commit, windowMs: 10_000 });
    vi.advanceTimersByTime(9_999);
    expect(commit).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(commit).toHaveBeenCalledOnce();
    noNetwork();
  });

  it("an undone gate is never written at all", () => {
    const toast = createToast(createToastStore());
    const commit = vi.fn();
    const undo = vi.fn();
    const handle = toast.undoable({ text: "Signed off as reviewer", commit, undo });
    toast.act(handle.id);
    vi.advanceTimersByTime(60_000);
    expect(commit).not.toHaveBeenCalled();
    expect(undo).toHaveBeenCalledOnce();
    noNetwork();
  });

  it("the toast shows only the caller's words: no gate state of its own", () => {
    const store = createToastStore();
    const toast = createToast(store);
    toast.undoable({ text: "Signed off as reviewer", commit: () => undefined });
    expect(store.list().map((t) => [t.kind, t.text, t.action])).toEqual([
      ["success", "Signed off as reviewer", "Undo"],
    ]);
  });
});
