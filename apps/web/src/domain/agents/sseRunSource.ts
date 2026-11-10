// P-10-T35 (SPEC-647 AC-T1, AC-T3; ADR-232 proposed; C6 v2): the run's SSE source behind the E6
// `RunSource` interface, and the source factory the dock uses.
//
// - `SseRunSource` listens to `GET /v1/agent-runs/{id}/events` (identifiers only: `seq`, the event
//   type, a state code). Each event at a `seq` past the cursor fetches the new items through REST
//   (`after_seq` = the cursor), so a page is the same `RunItemsOut` the polling source pushes and
//   the store applies it once; an event over 64 KB arrives `ref_only` and is fetched the same way.
//   `resync` refetches from 0 (the page says `resync`, so the store replaces the feed); `locked`
//   stops the stream and reports the not-allowed error; a terminal run state stops it for good.
// - When the stream dies (the runtime's retries spent, or the iterator throws), the source falls
//   back to `PollingRunSource` at 2 s from the same cursor, so no event is lost. A clean end of
//   the iterator is not a death (the runtime reconnects on its own).
// - `runSourceFor` picks SSE behind `realtime.sse` and polling otherwise; polling stays the
//   fallback everywhere.

import { client } from "@abacus/api-client/client";
import type { RunItemsOut } from "@abacus/api-client";
import { isActive } from "./feedCore";
import {
  type FetchPage,
  PollingRunSource,
  type RunSource,
  type RunSourceListener,
  type RunSourceEvent,
  type Visibility,
} from "./runSource";

export const FALLBACK_POLL_MS = 2_000;
export const SSE_MAX_ATTEMPTS = 3;

/** One frame of the run stream: its event name, its id (the run's `seq`) and its data. */
export interface RunStreamFrame {
  event: string;
  seq: number;
  data: Record<string, unknown>;
}

export type RunStreamOpener = (options: {
  runId: string;
  lastEventId?: string;
  signal: AbortSignal;
  maxAttempts: number;
}) => AsyncIterable<RunStreamFrame>;

/** A queue that turns the runtime's `onSseEvent` callbacks into an async iterable of frames. */
async function* frames(
  runId: string,
  signal: AbortSignal,
  lastEventId: string | undefined,
  maxAttempts: number,
): AsyncGenerator<RunStreamFrame> {
  const queue: RunStreamFrame[] = [];
  // Mutated from the stream's callbacks: an object, so the checks below read its live values.
  const state: { wake: (() => void) | null; finished: boolean; failure: Error | null } = {
    wake: null,
    finished: false,
    failure: null,
  };
  const asError = (error: unknown): Error =>
    error instanceof Error ? error : new Error(String(error));
  const push = (frame: RunStreamFrame): void => {
    queue.push(frame);
    state.wake?.();
  };
  void (async () => {
    try {
      const { stream } = await client.sse.get<Record<string, unknown>>({
        url: "/v1/agent-runs/{run_id}/events",
        path: { run_id: runId },
        security: [{ scheme: "bearer", type: "http" }],
        ...(lastEventId === undefined ? {} : { headers: { "Last-Event-ID": lastEventId } }),
        signal,
        sseMaxRetryAttempts: maxAttempts,
        sseDefaultRetryDelay: 1_000,
        sseMaxRetryDelay: 10_000,
        onSseError: (error: unknown) => {
          state.failure = asError(error);
        },
        onSseEvent: (event) => {
          const data = (event.data as Record<string, unknown> | undefined) ?? {};
          const seq = Number(event.id ?? data["seq"] ?? 0);
          push({ event: event.event ?? "message", seq, data });
        },
      });
      // Frames arrive through onSseEvent, with their event names; this drains the stream.
      const reader = stream[Symbol.asyncIterator]();
      while (!(await reader.next()).done) {
        // each frame was handled by onSseEvent
      }
    } catch (error) {
      state.failure = asError(error);
    } finally {
      state.finished = true;
      state.wake?.();
    }
  })();
  for (;;) {
    if (queue.length > 0) {
      yield queue.shift() as RunStreamFrame;
      continue;
    }
    if (state.finished) {
      if (state.failure !== null && !signal.aborted) throw state.failure;
      return;
    }
    await new Promise<void>((resolve) => {
      state.wake = resolve;
    });
    state.wake = null;
  }
}

const defaultOpener: RunStreamOpener = ({ runId, lastEventId, signal, maxAttempts }) =>
  frames(runId, signal, lastEventId, maxAttempts);

/** The not-allowed error a `locked` frame reports (a wall or a lost grant). */
export class RunStreamLocked extends Error {
  readonly status = 404;
  constructor() {
    super("locked");
  }
}

const TERMINAL_EVENTS = new Set(["succeeded", "failed", "cancelled"]);

export class SseRunSource implements RunSource {
  private readonly listeners = new Set<RunSourceListener>();
  private abort: AbortController | null = null;
  private cursor = 0;
  private started = false;
  private done = false;
  private fallback: PollingRunSource | null = null;
  private fetching: Promise<void> = Promise.resolve();

  constructor(
    private readonly runId: string,
    private readonly fetchPage: FetchPage,
    private readonly options: {
      open?: RunStreamOpener;
      visibility?: Visibility;
      fallbackMs?: number;
      onStateChange?: (state: string) => void;
    } = {},
  ) {}

  subscribe(listener: RunSourceListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private emit(event: RunSourceEvent): void {
    for (const listener of this.listeners) listener(event);
  }

  /** Whether the source fell back to polling (the stream died). */
  get polling(): boolean {
    return this.fallback !== null;
  }

  start(): void {
    if (this.started || this.done) return;
    this.started = true;
    const abort = new AbortController();
    this.abort = abort;
    // The first page through REST, then the stream from its cursor.
    this.fetching = this.pull(0).then(() => this.listen(abort));
  }

  stop(): void {
    this.done = true;
    this.abort?.abort();
    this.abort = null;
    this.fallback?.stop();
    this.fallback = null;
  }

  private async pull(after: number): Promise<RunItemsOut | null> {
    try {
      const page = await this.fetchPage(after);
      if (this.done) return null;
      this.cursor = page.resync ? page.last_seq : Math.max(this.cursor, page.last_seq);
      this.emit({ kind: "page", page });
      if (!isActive(page.run)) this.stop();
      return page;
    } catch (error) {
      this.emit({ kind: "error", error });
      return null;
    }
  }

  /** Read live: `stop()` may run while a stream is awaited. */
  private get stopped(): boolean {
    return this.done;
  }

  private async listen(abort: AbortController): Promise<void> {
    if (this.done) return;
    const open = this.options.open ?? defaultOpener;
    try {
      for await (const frame of open({
        runId: this.runId,
        lastEventId: this.cursor > 0 ? String(this.cursor) : undefined,
        signal: abort.signal,
        maxAttempts: SSE_MAX_ATTEMPTS,
      } as Parameters<RunStreamOpener>[0])) {
        if (this.stopped) return;
        if (frame.event === "locked") {
          this.emit({ kind: "error", error: new RunStreamLocked() });
          this.stop();
          return;
        }
        if (frame.event === "resync") {
          await this.pull(0);
          continue;
        }
        const state = typeof frame.data["state"] === "string" ? frame.data["state"] : null;
        if (frame.event === "run.state_changed" && state !== null)
          this.options.onStateChange?.(state);
        if (frame.seq > this.cursor || frame.data["ref_only"] === true) {
          await this.pull(this.cursor);
        }
        if (state !== null && TERMINAL_EVENTS.has(state)) {
          this.stop();
          return;
        }
      }
      // A clean end is not a death: the runtime reconnects inside `client.sse` (with
      // Last-Event-ID) until its retries are spent, and that surfaces as an error, below.
    } catch {
      if (!this.stopped) this.fallBack();
    }
  }

  /** The stream died: poll every 2 s from the same cursor (no event lost). */
  private fallBack(): void {
    if (this.fallback !== null || this.done) return;
    const polling = new PollingRunSource(
      // The poller's own cursor starts at 0; the stream's carries on, so nothing is fetched twice.
      (after) => this.fetchPage(Math.max(after, this.cursor)),
      {
        intervalMs: this.options.fallbackMs ?? FALLBACK_POLL_MS,
        ...(this.options.visibility ? { visibility: this.options.visibility } : {}),
      },
    );
    polling.subscribe((event) => {
      if (event.kind === "page") {
        this.cursor = Math.max(this.cursor, event.page.last_seq);
      }
      this.emit(event);
    });
    this.fallback = polling;
    polling.start();
  }

  /** For tests: resolves once the first page and the stream's listening have run. */
  settled(): Promise<void> {
    return this.fetching;
  }
}

/** SSE behind `realtime.sse`, else polling; the dock and every run surface take their source here. */
export function runSourceFor(
  runId: string,
  fetchPage: FetchPage,
  options: { sse: boolean; onStateChange?: (state: string) => void },
): RunSource {
  if (options.sse) {
    return new SseRunSource(runId, fetchPage, {
      ...(options.onStateChange ? { onStateChange: options.onStateChange } : {}),
    });
  }
  return new PollingRunSource(fetchPage);
}
