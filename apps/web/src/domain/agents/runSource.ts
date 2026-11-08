// E6 core (P-09-T05; SPEC-648 AC-8; DEC-2811): where a run's items come from, and the store a
// surface reads them through.
//
// - `RunSource` is the one interface every source implements: the polling source here, the
//   scripted source for fixtures and specimens, and P-10's `SseRunSource` (P-10-T35) later. A
//   source pushes pages; it never decides what a surface shows.
// - `RunStore` holds one run's feed and applies pages in `seq` order through `applyItems` (each
//   item once; `resync` replaces everything). Surfaces read it with `useRunStore`, which is
//   `useSyncExternalStore`, so a render never sees a torn feed.
// - `PollingRunSource` polls `GET /v1/agent-runs/{id}/items?after_seq=` every 1.5 s while the run
//   is active and the tab visible, with the `after_seq` cursor; it stops for good on a terminal
//   state and pauses while the tab is hidden.
// - `ScriptedRunSource` plays a fixture's pages on a clock (the mechanics of the handoff's
//   `lib/agents.js`; its scripts are the fixture's, never the kit's sample data). `?static=1`
//   freezes it: every page at once, so a screenshot or a parity capture is the final frame.

import type { RunItemsOut } from "@abacus/api-client";
import { useSyncExternalStore } from "react";
import { applyItems, EMPTY_FEED, isActive, POLL_MS, type RunFeed } from "./runFeed";

export type RunSourceEvent =
  { kind: "page"; page: RunItemsOut } | { kind: "error"; error: unknown };
export type RunSourceListener = (event: RunSourceEvent) => void;

export interface RunSource {
  /** Start pushing pages; idempotent. */
  start(): void;
  /** Stop for good: no page after this. */
  stop(): void;
  /** Listen to pages and errors; returns the unsubscribe. */
  subscribe(listener: RunSourceListener): () => void;
}

/** One run's feed; pages apply in `seq` order, `resync` replaces it. */
export class RunStore {
  private feed: RunFeed = EMPTY_FEED;
  private error: unknown = null;
  private readonly listeners = new Set<() => void>();

  getSnapshot = (): RunFeed => this.feed;
  getError = (): unknown => this.error;

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  apply(page: RunItemsOut): void {
    this.feed = applyItems(this.feed, page);
    this.error = null;
    this.emit();
  }

  fail(error: unknown): void {
    this.error = error;
    this.emit();
  }

  reset(): void {
    this.feed = EMPTY_FEED;
    this.error = null;
    this.emit();
  }

  /** Feed a source into the store; returns the detach. */
  connect(source: RunSource): () => void {
    const off = source.subscribe((event) => {
      if (event.kind === "page") this.apply(event.page);
      else this.fail(event.error);
    });
    source.start();
    return () => {
      off();
      source.stop();
    };
  }

  private emit(): void {
    for (const listener of this.listeners) listener();
  }
}

/** The store's feed, without tearing (React 18 external store). */
export function useRunStore(store: RunStore): RunFeed {
  return useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
}

class Emitter {
  private readonly listeners = new Set<RunSourceListener>();

  subscribe(listener: RunSourceListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  emit(event: RunSourceEvent): void {
    for (const listener of this.listeners) listener(event);
  }
}

export type FetchPage = (afterSeq: number) => Promise<RunItemsOut>;

export interface Visibility {
  hidden(): boolean;
  onChange(listener: () => void): () => void;
}

/** The document's visibility, or "always visible" outside a browser. */
export const documentVisibility: Visibility = {
  hidden: () => typeof document !== "undefined" && document.visibilityState === "hidden",
  onChange: (listener) => {
    if (typeof document === "undefined") return () => undefined;
    document.addEventListener("visibilitychange", listener);
    return () => {
      document.removeEventListener("visibilitychange", listener);
    };
  },
};

/** Polls while the run is active and the tab visible; stops on a terminal state. */
export class PollingRunSource implements RunSource {
  private readonly emitter = new Emitter();
  private timer: ReturnType<typeof setTimeout> | null = null;
  private cursor = 0;
  private running = false;
  private done = false;
  private inFlight = false;
  private offVisibility: (() => void) | null = null;

  constructor(
    private readonly fetchPage: FetchPage,
    private readonly options: { intervalMs?: number; visibility?: Visibility } = {},
  ) {}

  subscribe(listener: RunSourceListener): () => void {
    return this.emitter.subscribe(listener);
  }

  start(): void {
    if (this.running || this.done) return;
    this.running = true;
    const visibility = this.options.visibility ?? documentVisibility;
    this.offVisibility = visibility.onChange(() => {
      if (!visibility.hidden() && this.running && this.timer === null) void this.tick();
    });
    void this.tick();
  }

  stop(): void {
    this.running = false;
    this.done = true;
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
    this.offVisibility?.();
    this.offVisibility = null;
  }

  private stopped(): boolean {
    return !this.running;
  }

  private schedule(): void {
    if (!this.running) return;
    this.timer = setTimeout(() => {
      this.timer = null;
      void this.tick();
    }, this.options.intervalMs ?? POLL_MS);
  }

  private async tick(): Promise<void> {
    const visibility = this.options.visibility ?? documentVisibility;
    if (!this.running || this.inFlight) return;
    if (visibility.hidden()) return; // resumes on the next visibility change
    this.inFlight = true;
    try {
      const page = await this.fetchPage(this.cursor);
      if (this.stopped()) return; // stopped while the request was in flight
      this.cursor = page.resync ? page.last_seq : Math.max(this.cursor, page.last_seq);
      this.emitter.emit({ kind: "page", page });
      if (!isActive(page.run)) {
        this.stop(); // terminal: no more polling, ever
        return;
      }
    } catch (error) {
      this.emitter.emit({ kind: "error", error });
    } finally {
      this.inFlight = false;
    }
    this.schedule();
  }
}

export interface ScriptStep {
  /** The page this step adds. */
  page: RunItemsOut;
  /** How long after the previous step it arrives (ms). */
  afterMs: number;
}

/** Plays a fixture's pages on a clock; `freeze` (`?static=1`) delivers every page at once. */
export class ScriptedRunSource implements RunSource {
  private readonly emitter = new Emitter();
  private readonly timers: ReturnType<typeof setTimeout>[] = [];
  private started = false;

  constructor(
    private readonly script: readonly ScriptStep[],
    private readonly options: { freeze?: boolean } = {},
  ) {}

  subscribe(listener: RunSourceListener): () => void {
    return this.emitter.subscribe(listener);
  }

  start(): void {
    if (this.started) return;
    this.started = true;
    if (this.options.freeze === true) {
      for (const step of this.script) this.emitter.emit({ kind: "page", page: step.page });
      return;
    }
    let at = 0;
    for (const step of this.script) {
      at += step.afterMs;
      this.timers.push(
        setTimeout(() => {
          this.emitter.emit({ kind: "page", page: step.page });
        }, at),
      );
    }
  }

  stop(): void {
    for (const timer of this.timers) clearTimeout(timer);
    this.timers.length = 0;
  }
}

/** `?static=1` on the page: scripted sources freeze on their last frame. */
export function staticRequested(
  search: string = typeof location === "undefined" ? "" : location.search,
): boolean {
  return new URLSearchParams(search).get("static") === "1";
}
