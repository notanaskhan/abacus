// The toast store (F-05-T21; E3; C-21 `lib/toast.js` semantics, kept exact). A module store read
// with `useSyncExternalStore`, one per window: the host renders it, everything else calls `toast`.
//
// - Kinds: success, info, warning, error, running. Auto-dismiss 4 s, 8 s with an action; error and
//   running persist until closed or updated. Hover pauses; resuming keeps at least 600 ms.
// - At most 3 live: a 4th dismisses the oldest. A dismissed toast stays 180 ms with `leaving`.
// - The store never writes anything of its own (INV-1): Undo calls only the caller's command.
//
// Timers measure elapsed time, not business time, so they read `performance.now()`, never the
// clock (format.ts and clock.tsx own business time).

export type ToastKind = "success" | "info" | "warning" | "error" | "running";

export interface ToastInput {
  kind?: ToastKind | undefined;
  /** Past tense, specific, under 60 characters, no emoji, no exclamation mark (`copyProblems`). */
  text: string;
  /** One action only: "Undo", "View", "Retry". */
  action?: string | null | undefined;
  /** Runs after the toast is dismissed. */
  onAction?: (() => void) | null | undefined;
  /** A close button. Default: on for error, off otherwise. */
  close?: boolean | undefined;
  /** Stay until dismissed. */
  persist?: boolean | undefined;
  /** Override the auto-dismiss, in ms. */
  duration?: number | undefined;
}

export interface Toast {
  id: string;
  kind: ToastKind;
  text: string;
  action: string | null;
  close: boolean;
  persist: boolean;
  /** True for 180 ms before removal, so the host can fade it. */
  leaving: boolean;
  /** Hovered. */
  paused: boolean;
}

interface Entry extends Toast {
  onAction: (() => void) | null;
  duration: number | undefined;
  /** Time left when paused (at least 600 ms). */
  left: number | null;
  until: number | null;
}

export const MAX_LIVE = 3;
export const LEAVE_MS = 180;
export const MIN_RESUME_MS = 600;
export const DEFAULT_MS = 4000;
export const ACTION_MS = 8000;
/** DEC-24: the Undo window. */
export const UNDO_MS = 10_000;

/** Auto-dismiss: 4 s, 8 s with an action; error and running persist until closed or updated. */
export function duration(
  t: Pick<ToastInput, "kind" | "persist" | "duration" | "action">,
): number | null {
  if (t.persist === true || t.kind === "error" || t.kind === "running") return null;
  return t.duration ?? (t.action ? ACTION_MS : DEFAULT_MS);
}

/** Errors are alerts (assertive); everything else is a polite status. */
export function aria(kind: ToastKind): {
  role: "alert" | "status";
  "aria-live": "assertive" | "polite";
} {
  return kind === "error"
    ? { role: "alert", "aria-live": "assertive" }
    : { role: "status", "aria-live": "polite" };
}

/** The copy rules (C-21 §5): what a reviewer or test should flag. */
export function copyProblems(text: string): string[] {
  const problems: string[] = [];
  if (text.length > 60) problems.push("over 60 characters");
  if (text.includes("!")) problems.push("exclamation mark");
  if (/\p{Extended_Pictographic}/u.test(text)) problems.push("emoji");
  return problems;
}

const now = (): number => performance.now();

export interface ToastStore {
  show: (input: ToastInput | string) => string;
  update: (id: string, patch: Partial<ToastInput>) => void;
  dismiss: (id: string) => void;
  act: (id: string) => void;
  pause: (id: string) => void;
  resume: (id: string) => void;
  clear: () => void;
  /** Tests only: drop every toast now, without the 180 ms leave, so none outlives its test. */
  reset: () => void;
  list: () => readonly Toast[];
  subscribe: (listener: () => void) => () => void;
}

export function createToastStore(): ToastStore {
  let entries: Entry[] = [];
  let snapshot: readonly Toast[] = [];
  let seq = 0;
  const timers = new Map<string, ReturnType<typeof setTimeout>>();
  const listeners = new Set<() => void>();

  const find = (id: string): Entry | undefined => entries.find((e) => e.id === id);

  function emit(): void {
    snapshot = entries.map(
      ({ id, kind, text, action, close, persist, leaving, paused }): Toast => ({
        id,
        kind,
        text,
        action,
        close,
        persist,
        leaving,
        paused,
      }),
    );
    for (const listener of [...listeners]) listener();
  }

  function stop(id: string): void {
    const timer = timers.get(id);
    if (timer !== undefined) clearTimeout(timer);
    timers.delete(id);
  }

  function arm(e: Entry): void {
    stop(e.id);
    e.until = null;
    const ms = e.left ?? duration(e);
    if (ms === null || e.paused) return;
    e.until = now() + ms;
    timers.set(
      e.id,
      setTimeout(() => {
        store.dismiss(e.id);
      }, ms),
    );
  }

  const store: ToastStore = {
    show(input) {
      const o: ToastInput = typeof input === "string" ? { text: input } : input;
      const kind = o.kind ?? "success";
      const e: Entry = {
        id: `t${String(++seq)}`,
        kind,
        text: o.text,
        action: o.action ?? null,
        onAction: o.onAction ?? null,
        close: o.close ?? kind === "error",
        persist: o.persist === true,
        duration: o.duration,
        leaving: false,
        paused: false,
        left: null,
        until: null,
      };
      entries = [...entries, e];
      arm(e);
      const live = entries.filter((x) => !x.leaving);
      for (const old of live.slice(0, Math.max(0, live.length - MAX_LIVE))) store.dismiss(old.id);
      emit();
      return e.id;
    },
    update(id, patch) {
      const e = find(id);
      if (e === undefined || e.leaving) return;
      if (patch.kind !== undefined) e.kind = patch.kind;
      if (patch.text !== undefined) e.text = patch.text;
      if (patch.action !== undefined) e.action = patch.action;
      if (patch.onAction !== undefined) e.onAction = patch.onAction;
      if (patch.persist !== undefined) e.persist = patch.persist;
      if (patch.duration !== undefined) e.duration = patch.duration;
      if (patch.close !== undefined) e.close = patch.close;
      else if (patch.kind !== undefined) e.close = e.kind === "error";
      e.left = null;
      arm(e);
      emit();
    },
    dismiss(id) {
      const e = find(id);
      if (e === undefined || e.leaving) return;
      stop(id);
      e.leaving = true;
      emit();
      setTimeout(() => {
        entries = entries.filter((x) => x.id !== id);
        emit();
      }, LEAVE_MS);
    },
    act(id) {
      const e = find(id);
      if (e === undefined || e.leaving) return;
      const run = e.onAction;
      store.dismiss(id);
      run?.();
    },
    pause(id) {
      const e = find(id);
      if (e === undefined || e.paused) return;
      e.paused = true;
      if (e.until !== null) e.left = Math.max(MIN_RESUME_MS, e.until - now());
      stop(id);
      emit();
    },
    resume(id) {
      const e = find(id);
      if (e === undefined || !e.paused) return;
      e.paused = false;
      arm(e);
      emit();
    },
    clear() {
      for (const e of [...entries]) store.dismiss(e.id);
    },
    reset() {
      for (const id of [...timers.keys()]) stop(id);
      entries = [];
      emit();
    },
    list() {
      return snapshot;
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
  return store;
}

export interface UndoableInput {
  text: string;
  /**
   * Deferred commit (gates, §7.5): runs when the window closes, the page is leaving, or `flush()`
   * is called, unless Undo came first. Omit it when the write already committed.
   */
  commit?: (() => void) | undefined;
  /** The caller's compensating command (it writes `*.undone`); the only thing Undo calls. */
  undo?: (() => void) | undefined;
  windowMs?: number | undefined;
}

export interface UndoableHandle {
  id: string;
  /** Commit now (a deferred commit only). */
  flush: () => void;
  /** The module reports its external effect has started: Undo is no longer offered. */
  started: () => void;
}

export interface RunningHandle {
  id: string;
  /** Replace the running toast in place: "Uploaded 3 of 4 files", warning, View. */
  update: (patch: Partial<ToastInput>) => void;
  succeed: (text: string, patch?: Omit<Partial<ToastInput>, "kind" | "text">) => void;
  fail: (text: string, patch?: Omit<Partial<ToastInput>, "kind" | "text">) => void;
}

export interface RunningOptions {
  /**
   * A job that never reports back must not leave its toast forever (C-21 open question): after
   * this long the toast turns into a warning. Default 2 minutes; 0 keeps it until updated.
   */
  timeoutMs?: number | undefined;
  timeoutText?: string | undefined;
}

export const RUNNING_TIMEOUT_MS = 120_000;

/** The `toast` facade over one store: `show`, `undoable`, `running` and the store's controls. */
export function createToast(store: ToastStore) {
  function show(input: ToastInput | string, ms?: number): string {
    if (typeof input === "string" && ms !== undefined)
      return store.show({ text: input, duration: ms });
    return store.show(input);
  }

  function undoable({ text, commit, undo, windowMs = UNDO_MS }: UndoableInput): UndoableHandle {
    let settled = false;
    let id = "";
    const leaving = (): void => {
      finish();
    };
    function detach(): void {
      if (commit !== undefined && typeof window !== "undefined") {
        window.removeEventListener("pagehide", leaving);
      }
    }
    function finish(): void {
      if (settled) return;
      settled = true;
      detach();
      commit?.();
    }
    id = store.show({
      kind: "success",
      text,
      action: "Undo",
      duration: windowMs,
      onAction: () => {
        if (settled) return;
        settled = true;
        detach();
        undo?.();
      },
    });
    if (commit !== undefined) {
      if (typeof window !== "undefined") window.addEventListener("pagehide", leaving);
      setTimeout(finish, windowMs);
    }
    return {
      id,
      flush() {
        if (settled) return;
        finish();
        store.dismiss(id);
      },
      started() {
        if (commit === undefined) settled = true;
        store.update(id, { action: null, onAction: null, duration: DEFAULT_MS });
      },
    };
  }

  function running(
    text: string,
    {
      timeoutMs = RUNNING_TIMEOUT_MS,
      timeoutText = "Stopped waiting for an update",
    }: RunningOptions = {},
  ): RunningHandle {
    const id = store.show({ kind: "running", text });
    let timer: ReturnType<typeof setTimeout> | undefined;
    if (timeoutMs > 0) {
      timer = setTimeout(() => {
        store.update(id, { kind: "warning", text: timeoutText, close: true });
      }, timeoutMs);
    }
    const settle = (patch: Partial<ToastInput>): void => {
      if (timer !== undefined) clearTimeout(timer);
      timer = undefined;
      store.update(id, patch);
    };
    return {
      id,
      update: settle,
      succeed: (t, patch) => {
        settle({ ...patch, kind: "success", text: t });
      },
      fail: (t, patch) => {
        settle({ ...patch, kind: "error", text: t });
      },
    };
  }

  /** Legacy (TASK-101): a held action committed after the Undo window. Prefer `undoable`. */
  function deferred(message: string, commit: () => void, onUndo?: () => void): () => void {
    const handle = undoable({ text: message, commit, undo: onUndo });
    return () => {
      handle.flush();
    };
  }

  return {
    show,
    undoable,
    running,
    deferred,
    update: store.update,
    dismiss: store.dismiss,
    act: store.act,
    pause: store.pause,
    resume: store.resume,
    clear: store.clear,
  };
}
