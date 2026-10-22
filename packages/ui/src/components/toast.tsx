import { type JSX, useSyncExternalStore } from "react";
import { cn } from "../cn";
import { Icon } from "../icons";
import { useMotion } from "../motion";
import {
  type Toast as ToastItem,
  type ToastKind,
  type ToastStore,
  UNDO_MS,
  aria,
  createToast,
  createToastStore,
} from "./toast-store";

// Toasts (F-05-T21; E3; C-21): one espresso pill per message, bottom-centre at 24 px, stacking
// upward 8 apart, at most three. The store is `./toast-store`; this file is the host, the static
// specimen and the one store a window shares. Blocking errors never come here: they are an
// ErrorRow (C-20).

export { UNDO_MS };
export type { ToastItem, ToastKind };

/** The window's one toast store. */
export const toastStore = createToastStore();

/**
 * `toast.show({kind, text, action, onAction, close, persist, duration})`, `toast.undoable({text,
 * commit, undo, windowMs})`, `toast.running(text)` and the store's controls. `toast.show(text)` and
 * `toast.deferred(text, commit, undo)` keep the older calls working.
 */
export const toast = createToast(toastStore);

/** The live toasts, for a host or a test. */
export function useToasts(store: ToastStore = toastStore): readonly ToastItem[] {
  return useSyncExternalStore(store.subscribe, store.list, store.list);
}

function Glyph({ kind, animate }: { kind: ToastKind; animate: boolean }): JSX.Element {
  if (kind === "running") {
    return (
      <span
        aria-hidden="true"
        className="inline-flex size-[15px] shrink-0 items-center justify-center"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 14 14"
          focusable="false"
          className={cn("block", animate && "motion-spin")}
        >
          <circle
            cx="7"
            cy="7"
            r="6"
            fill="none"
            strokeWidth="1.6"
            className="stroke-on-dark/18"
          />
          <circle
            cx="7"
            cy="7"
            r="6"
            fill="none"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeDasharray="10.6 37.7"
            className="stroke-on-dark/72"
          />
        </svg>
      </span>
    );
  }
  if (kind === "info") {
    return <Icon name="info" size={15} className="shrink-0 text-on-dark/72" />;
  }
  const disc = {
    success: "bg-green",
    warning: "bg-amber",
    error: "bg-red",
  }[kind];
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex size-[15px] shrink-0 items-center justify-center rounded-pill text-card",
        disc,
      )}
    >
      {kind === "success" && (
        <Icon name="check" size={12} strokeWidth={2.4} className="size-[9px]" />
      )}
      {kind === "error" && <Icon name="x" size={12} strokeWidth={2.4} className="size-[9px]" />}
      {kind === "warning" && <span className="text-[11px] leading-none font-medium">!</span>}
    </span>
  );
}

export interface ToastViewProps {
  kind?: ToastKind;
  text: string;
  action?: string | null;
  close?: boolean;
  leaving?: boolean;
  /** Draw without the rise and the turning spinner (specimens, reduced motion). */
  still?: boolean;
  onAction?: () => void;
  onClose?: () => void;
  onPause?: () => void;
  onResume?: () => void;
}

/** One toast. The host renders these from the store; specimens render them directly. */
export function Toast({
  kind = "success",
  text,
  action = null,
  close = kind === "error",
  leaving = false,
  still = false,
  onAction,
  onClose,
  onPause,
  onResume,
}: ToastViewProps): JSX.Element {
  const animate = useMotion(still);
  return (
    <div
      {...aria(kind)}
      data-toast={kind}
      data-leaving={leaving ? "true" : undefined}
      aria-hidden={leaving ? true : undefined}
      onMouseEnter={onPause}
      onMouseLeave={onResume}
      onFocus={onPause}
      onBlur={onResume}
      className={cn(
        "pointer-events-auto inline-flex h-9 items-center gap-[8px] rounded-pill bg-espresso pl-[10px] text-body font-medium whitespace-nowrap text-on-dark shadow-e3",
        close ? "pr-[12px]" : "pr-[14px]",
        animate && "motion-toast-in",
        "transition-opacity duration-180",
        leaving && "pointer-events-none opacity-0",
      )}
    >
      <Glyph kind={kind} animate={animate} />
      <span>{text}</span>
      {action !== null && (
        <span className="ml-[2px] inline-flex h-5 items-center border-l-[0.5px] border-on-dark/18 pl-[10px]">
          <button
            type="button"
            onClick={onAction}
            className="rounded-[4px] text-body font-medium text-on-dark/86 transition-colors duration-180 hover:text-on-dark"
          >
            {action}
          </button>
        </span>
      )}
      {close && (
        <button
          type="button"
          aria-label="Dismiss"
          onClick={onClose}
          className="-mr-[6px] inline-flex size-5 items-center justify-center rounded-pill opacity-60 transition-opacity duration-180 hover:opacity-100"
        >
          <Icon name="x" size={12} />
        </button>
      )}
    </div>
  );
}

export interface ToastHostProps {
  /** Absolute inside a framed container (specimens) instead of fixed to the window. */
  contained?: boolean;
  /** Distance from the bottom, px. Always 24 in the app. */
  bottom?: number;
  /** The window's store unless a specimen brings its own. */
  store?: ToastStore;
}

/** Mount once per window, at the root. */
export function ToastHost({
  contained = false,
  bottom = 24,
  store = toastStore,
}: ToastHostProps): JSX.Element {
  const shown = useToasts(store);
  return (
    <div
      data-toast-host=""
      style={{ bottom }}
      className={cn(
        "pointer-events-none left-1/2 z-(--z-toast) flex -translate-x-1/2 flex-col items-center gap-[8px]",
        contained ? "absolute" : "fixed",
      )}
    >
      {shown.map((t) => (
        <Toast
          key={t.id}
          kind={t.kind}
          text={t.text}
          action={t.action}
          close={t.close}
          leaving={t.leaving}
          onAction={() => {
            store.act(t.id);
          }}
          onClose={() => {
            store.dismiss(t.id);
          }}
          onPause={() => {
            store.pause(t.id);
          }}
          onResume={() => {
            store.resume(t.id);
          }}
        />
      ))}
    </div>
  );
}

/** The older name for the host (TASK-101). */
export const Toaster = ToastHost;
