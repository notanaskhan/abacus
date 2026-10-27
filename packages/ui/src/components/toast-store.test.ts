import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ACTION_MS,
  DEFAULT_MS,
  LEAVE_MS,
  RUNNING_TIMEOUT_MS,
  UNDO_MS,
  aria,
  copyProblems,
  createToast,
  createToastStore,
  duration,
} from "./toast-store";

// The C-21 store (F-05-T21; lib/toast.js semantics) and the E2 Undo contract (DEC-24, INV-1).

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "performance"] });
});
afterEach(() => {
  vi.useRealTimers();
});

const live = (store: ReturnType<typeof createToastStore>) =>
  store.list().filter((t) => !t.leaving);

describe("auto-dismiss (C-21 §3)", () => {
  it("dismisses after 4 s, then keeps the toast 180 ms leaving", () => {
    const store = createToastStore();
    const id = store.show("Approved 3 adjustments");
    vi.advanceTimersByTime(DEFAULT_MS - 1);
    expect(store.list()[0]?.leaving).toBe(false);
    vi.advanceTimersByTime(1);
    expect(store.list()[0]).toMatchObject({ id, leaving: true });
    vi.advanceTimersByTime(LEAVE_MS);
    expect(store.list()).toEqual([]);
  });

  it("waits 8 s when there is an action", () => {
    const store = createToastStore();
    store.show({ text: "Reply sent to Matthew Douglas", action: "View" });
    vi.advanceTimersByTime(ACTION_MS - 1);
    expect(live(store)).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(live(store)).toHaveLength(0);
  });

  it("never dismisses error or running toasts on its own", () => {
    const store = createToastStore();
    store.show({ kind: "error", text: "Couldn’t connect to Cascadia Bank" });
    store.show({ kind: "running", text: "Uploading 4 files…" });
    vi.advanceTimersByTime(60_000);
    expect(live(store)).toHaveLength(2);
  });

  it("states the durations as the kit does", () => {
    expect(duration({ kind: "success" })).toBe(4000);
    expect(duration({ kind: "info", action: "View" })).toBe(8000);
    expect(duration({ kind: "success", duration: 1500 })).toBe(1500);
    expect(duration({ kind: "success", persist: true })).toBeNull();
    expect(duration({ kind: "error" })).toBeNull();
    expect(duration({ kind: "running" })).toBeNull();
  });
});

describe("the stack", () => {
  it("holds at three: a fourth dismisses the oldest", () => {
    const store = createToastStore();
    const first = store.show("One");
    store.show("Two");
    store.show("Three");
    store.show("Four");
    expect(live(store).map((t) => t.text)).toEqual(["Two", "Three", "Four"]);
    expect(store.list().find((t) => t.id === first)?.leaving).toBe(true);
  });

  it("closes errors by default and nothing else", () => {
    const store = createToastStore();
    store.show({ kind: "error", text: "Couldn’t connect" });
    store.show({ kind: "success", text: "Saved" });
    expect(store.list().map((t) => t.close)).toEqual([true, false]);
  });
});

describe("hover", () => {
  it("pauses, and resuming keeps at least 600 ms", () => {
    const store = createToastStore();
    const id = store.show("Saved");
    vi.advanceTimersByTime(3900);
    store.pause(id);
    vi.advanceTimersByTime(10_000);
    expect(live(store)).toHaveLength(1);
    store.resume(id);
    vi.advanceTimersByTime(599);
    expect(live(store)).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(live(store)).toHaveLength(0);
  });

  it("resumes with the time that was left when more than 600 ms remained", () => {
    const store = createToastStore();
    const id = store.show("Saved");
    vi.advanceTimersByTime(1000);
    store.pause(id);
    store.resume(id);
    vi.advanceTimersByTime(2999);
    expect(live(store)).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(live(store)).toHaveLength(0);
  });
});

describe("update and act", () => {
  it("update changes the toast in place and re-arms its timer", () => {
    const store = createToastStore();
    const id = store.show({ kind: "running", text: "Uploading 4 files…" });
    vi.advanceTimersByTime(30_000);
    store.update(id, { kind: "warning", text: "Uploaded 3 of 4 files", action: "View" });
    expect(store.list()).toHaveLength(1);
    expect(store.list()[0]).toMatchObject({ id, kind: "warning", action: "View" });
    vi.advanceTimersByTime(ACTION_MS - 1);
    expect(live(store)).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(live(store)).toHaveLength(0);
  });

  it("updating to an error turns the close on, unless the patch says otherwise", () => {
    const store = createToastStore();
    const a = store.show({ kind: "running", text: "Connecting…" });
    const b = store.show({ kind: "running", text: "Connecting…" });
    store.update(a, { kind: "error", text: "Couldn’t connect" });
    store.update(b, { kind: "error", text: "Couldn’t connect", close: false });
    expect(store.list().map((t) => t.close)).toEqual([true, false]);
  });

  it("act dismisses, then runs onAction", () => {
    const store = createToastStore();
    const order: string[] = [];
    const id = store.show({
      text: "Couldn’t connect",
      kind: "error",
      action: "Retry",
      onAction: () => {
        order.push(store.list()[0]?.leaving === true ? "after dismiss" : "before dismiss");
      },
    });
    store.act(id);
    expect(order).toEqual(["after dismiss"]);
  });

  it("clear dismisses every toast", () => {
    const store = createToastStore();
    store.show("One");
    store.show({ kind: "error", text: "Two" });
    store.clear();
    expect(live(store)).toHaveLength(0);
  });

  it("reset drops every toast at once, leaving ones included, and stops their timers", () => {
    const store = createToastStore();
    store.show("One");
    store.clear();
    store.show({ kind: "error", text: "Two" });
    store.reset();
    expect(store.list()).toHaveLength(0);
    store.show("Three");
    vi.advanceTimersByTime(LEAVE_MS);
    expect(store.list().map((t) => t.text)).toEqual(["Three"]);
  });

  it("returns the same snapshot until something changes", () => {
    const store = createToastStore();
    store.show("One");
    expect(store.list()).toBe(store.list());
  });
});

describe("undoable (E2; DEC-24; INV-1)", () => {
  it("Undo inside the window calls only the compensating command, and never commits", () => {
    const toast = createToast(createToastStore());
    const commit = vi.fn();
    const undo = vi.fn();
    const handle = toast.undoable({ text: "Approved 3 adjustments", commit, undo });
    vi.advanceTimersByTime(UNDO_MS - 1);
    toast.act(handle.id);
    vi.advanceTimersByTime(UNDO_MS);
    expect(undo).toHaveBeenCalledOnce();
    expect(commit).not.toHaveBeenCalled();
  });

  it("a deferred commit runs once when the window closes", () => {
    const store = createToastStore();
    const toast = createToast(store);
    const commit = vi.fn();
    const handle = toast.undoable({ text: "Signed off", commit });
    vi.advanceTimersByTime(UNDO_MS - 1);
    expect(commit).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(commit).toHaveBeenCalledOnce();
    toast.act(handle.id);
    handle.flush();
    expect(commit).toHaveBeenCalledOnce();
  });

  it("flush commits at once; leaving the page commits too", () => {
    const toast = createToast(createToastStore());
    const flushed = vi.fn();
    toast.undoable({ text: "Signed off", commit: flushed }).flush();
    expect(flushed).toHaveBeenCalledOnce();
    const leaving = vi.fn();
    toast.undoable({ text: "Signed off", commit: leaving });
    window.dispatchEvent(new Event("pagehide"));
    expect(leaving).toHaveBeenCalledOnce();
  });

  it("with no commit, the store issues no write of its own: Undo is the caller's command alone", () => {
    const toast = createToast(createToastStore());
    const undo = vi.fn();
    const handle = toast.undoable({ text: "Archived Northwind", undo });
    vi.advanceTimersByTime(UNDO_MS + LEAVE_MS);
    expect(undo).not.toHaveBeenCalled();
    toast.act(handle.id);
    expect(undo).not.toHaveBeenCalled();
  });

  it("started() withdraws Undo once the effect has begun", () => {
    const store = createToastStore();
    const toast = createToast(store);
    const undo = vi.fn();
    const handle = toast.undoable({ text: "Request sent", undo });
    handle.started();
    expect(store.list()[0]?.action).toBeNull();
    toast.act(handle.id);
    expect(undo).not.toHaveBeenCalled();
  });

  it("keeps the older deferred() call: commit after ten seconds unless undone", () => {
    const toast = createToast(createToastStore());
    const commit = vi.fn();
    toast.deferred("Sent", commit);
    vi.advanceTimersByTime(UNDO_MS);
    expect(commit).toHaveBeenCalledOnce();
  });
});

describe("running", () => {
  it("settles in place to success or error", () => {
    const store = createToastStore();
    const toast = createToast(store);
    const job = toast.running("Connecting to Cascadia Bank…");
    job.succeed("Connected Cascadia Bank");
    expect(store.list()).toHaveLength(1);
    expect(store.list()[0]).toMatchObject({ id: job.id, kind: "success" });
    const other = toast.running("Uploading 4 files…");
    other.fail("Couldn’t upload 4 files", { action: "Retry" });
    expect(store.list().find((t) => t.id === other.id)).toMatchObject({
      kind: "error",
      close: true,
      action: "Retry",
    });
  });

  it("a job that never reports back turns into a warning instead of staying forever", () => {
    const store = createToastStore();
    const toast = createToast(store);
    toast.running("Uploading 4 files…");
    vi.advanceTimersByTime(RUNNING_TIMEOUT_MS);
    expect(store.list()[0]).toMatchObject({ kind: "warning", close: true });
  });

  it("show(text, ms) keeps the older call shape", () => {
    const store = createToastStore();
    const toast = createToast(store);
    toast.show("Saved", 1000);
    vi.advanceTimersByTime(1000);
    expect(live(store)).toHaveLength(0);
  });
});

describe("aria and copy", () => {
  it("errors are assertive alerts; everything else a polite status", () => {
    expect(aria("error")).toEqual({ role: "alert", "aria-live": "assertive" });
    for (const kind of ["success", "info", "warning", "running"] as const) {
      expect(aria(kind)).toEqual({ role: "status", "aria-live": "polite" });
    }
  });

  it("flags copy that breaks the rules", () => {
    expect(copyProblems("Approved 3 adjustments")).toEqual([]);
    expect(copyProblems("Saved!")).toEqual(["exclamation mark"]);
    expect(copyProblems("Saved 🎉")).toEqual(["emoji"]);
    expect(copyProblems("x".repeat(61))).toEqual(["over 60 characters"]);
  });
});
