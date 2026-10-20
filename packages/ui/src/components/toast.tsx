import { type JSX, useSyncExternalStore } from "react";

// Toasts (TASK-101, the plan's C-13): one espresso pill at the bottom centre. A deferred toast
// holds its action for ten seconds so Undo truly undoes: nothing is sent until the time is up
// (or the page is leaving, when it's sent at once).

export const UNDO_MS = 10_000;

interface ToastItem {
  id: number;
  message: string;
  undo?: () => void;
}

let items: ToastItem[] = [];
let next = 1;
const listeners = new Set<() => void>();

function emit(): void {
  for (const l of listeners) l();
}

function remove(id: number): void {
  items = items.filter((t) => t.id !== id);
  emit();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** A plain toast, gone after a few seconds. */
function show(message: string, ms = 4000): void {
  const id = next++;
  items = [...items.slice(-2), { id, message }];
  emit();
  setTimeout(() => {
    remove(id);
  }, ms);
}

/** A held action: `commit` runs after ten seconds unless the person clicks Undo. Returns a
 * function that commits at once (for flushing). */
function deferred(message: string, commit: () => void, onUndo?: () => void): () => void {
  const id = next++;
  let settled = false;
  const finish = (): void => {
    if (settled) return;
    settled = true;
    window.removeEventListener("pagehide", finish);
    remove(id);
    commit();
  };
  const undo = (): void => {
    if (settled) return;
    settled = true;
    window.removeEventListener("pagehide", finish);
    remove(id);
    onUndo?.();
  };
  items = [...items.slice(-2), { id, message, undo }];
  emit();
  window.addEventListener("pagehide", finish);
  setTimeout(finish, UNDO_MS);
  return finish;
}

export const toast = { show, deferred };

/** Mount once near the root. */
export function Toaster(): JSX.Element {
  const shown = useSyncExternalStore(
    subscribe,
    () => items,
    () => items,
  );
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 bottom-6 z-[60] flex flex-col items-center gap-2"
    >
      {shown.map((t) => (
        <div
          key={t.id}
          role="status"
          className="pointer-events-auto flex h-9 items-center gap-3 rounded-full bg-espresso pr-1.5 pl-3.5 text-[13px] font-medium text-on-dark shadow-e3 animate-[toast-in_200ms_var(--ease-out)]"
        >
          <span>{t.message}</span>
          {t.undo !== undefined ? (
            <button
              type="button"
              onClick={t.undo}
              className="h-[26px] rounded-full bg-on-dark/14 px-3 text-[12.5px] hover:bg-on-dark/22"
            >
              Undo
            </button>
          ) : (
            <span className="w-2" />
          )}
        </div>
      ))}
    </div>
  );
}
