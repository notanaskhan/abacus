// The real-time client (P-10-T30; ADR-232 proposed; C6 v2; SPEC-647 AC-T1, AC-T3, AC-T5, AC-T7).
//
// One SSE stream per tab on `GET /v1/events`, through the generated fetch-based SSE runtime (so the
// bearer header and the tenant come from the client's own interceptors), with backoff and
// `Last-Event-ID` resumption from the runtime. Events carry identifiers only; domains register how
// a topic maps to their query keys, and an `invalidate` refetches only the matching keys (never a
// blanket refetch). `notice` refreshes the bell; `resync` refetches every registered topic; `locked`
// clears the cache and tells listeners to show the not-allowed state (a wall or a lost grant).
// After three failed connections the client stops and every surface polls instead: 5 s for an open
// record, 30 s for a list, 60 s for the bell (polling is the permanent fallback and every surface is
// correct on it alone). Gated by `realtime.sse`: off, nothing connects and everything polls.

import { client } from "@abacus/api-client/client";
import type { QueryClient, QueryKey } from "@tanstack/react-query";

/** An event as `InvalidationEventOut` carries it (identifiers and enums only, AC-T2). */
export interface RealtimeEvent {
  seq: number;
  type: "stream" | "invalidate" | "notice" | "locked" | "resync";
  topic?: string | null;
  ref_type?: string | null;
  ref_id?: string | null;
  version?: number | null;
}

/** What a domain registers for a topic kind ("engagement", "run", "user", …). */
export type TopicKeys = (topic: string, event: RealtimeEvent) => readonly QueryKey[];

export type PollKind = "record" | "list" | "bell";
export const POLL_MS: Readonly<Record<PollKind, number>> = {
  record: 5_000,
  list: 30_000,
  bell: 60_000,
};
export const MAX_FAILURES = 3;

export type RealtimeStatus = "off" | "connecting" | "live" | "polling" | "locked";

/** Opens the stream; the default is the generated SSE runtime. Tests pass a script. */
export type StreamOpener = (options: {
  topics: readonly string[];
  signal: AbortSignal;
  lastEventId?: string;
  onError: (error: unknown) => void;
  maxAttempts: number;
}) => AsyncIterable<RealtimeEvent>;

async function* generated(
  topics: readonly string[],
  signal: AbortSignal,
  onError: (error: unknown) => void,
  maxAttempts: number,
): AsyncGenerator<RealtimeEvent> {
  const { stream } = await client.sse.get<RealtimeEvent>({
    url: "/v1/events",
    query: { topics: topics.join(",") },
    security: [{ scheme: "bearer", type: "http" }],
    signal,
    onSseError: onError,
    sseMaxRetryAttempts: maxAttempts,
    sseDefaultRetryDelay: 1_000,
    sseMaxRetryDelay: 30_000,
  });
  yield* stream as AsyncIterable<RealtimeEvent>;
}

const defaultOpener: StreamOpener = ({ topics, signal, onError, maxAttempts }) =>
  generated(topics, signal, onError, maxAttempts);

const registries = new Map<string, TopicKeys>();

/** A domain says which of its query keys a topic kind's events touch (at module load). */
export function registerTopicKeys(kind: string, keys: TopicKeys): void {
  registries.set(kind, keys);
}

function kindOf(topic: string): string {
  const colon = topic.indexOf(":");
  return colon === -1 ? topic : topic.slice(0, colon);
}

export class RealtimeClient {
  private status: RealtimeStatus = "off";
  private failures = 0;
  private abort: AbortController | null = null;
  private topics: string[] = [];
  private readonly listeners = new Set<(status: RealtimeStatus) => void>();

  constructor(
    private readonly queryClient: QueryClient,
    private readonly open: StreamOpener = defaultOpener,
    private readonly bellKey: QueryKey = ["notifications"],
  ) {}

  get state(): RealtimeStatus {
    return this.status;
  }

  /** Whether surfaces should poll now (off, polling after failures, or locked). */
  get polling(): boolean {
    return this.status !== "live" && this.status !== "connecting";
  }

  subscribe(listener: (status: RealtimeStatus) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private set(status: RealtimeStatus): void {
    if (this.status === status) return;
    this.status = status;
    for (const listener of this.listeners) listener(status);
  }

  /** Connect (or reconnect) for these topics; one stream at a time per tab. */
  async start(topics: readonly string[]): Promise<void> {
    this.stop();
    this.topics = [...topics];
    const abort = new AbortController();
    this.abort = abort;
    this.set("connecting");
    try {
      for await (const event of this.open({
        topics: this.topics,
        signal: abort.signal,
        maxAttempts: MAX_FAILURES,
        onError: () => {
          this.failures += 1;
        },
      })) {
        if (abort.signal.aborted) return;
        this.failures = 0;
        if (this.status !== "locked") this.set("live");
        await this.handle(event);
        if (this.status === "locked") {
          abort.abort();
          return;
        }
      }
    } catch {
      this.failures += 1;
    }
    if (abort.signal.aborted) return;
    // The runtime gave up after its retries, or the server closed for good: poll from here on.
    this.set("polling");
  }

  stop(): void {
    this.abort?.abort();
    this.abort = null;
    if (this.status !== "locked") this.set("off");
  }

  /** Refetch only the query keys the event's topic maps to (AC-T1). */
  async handle(event: RealtimeEvent): Promise<void> {
    switch (event.type) {
      case "stream":
        return;
      case "notice":
        await this.queryClient.invalidateQueries({ queryKey: this.bellKey });
        return;
      case "locked":
        this.queryClient.clear();
        this.set("locked");
        return;
      case "resync":
        await Promise.all(this.topics.map((topic) => this.invalidateTopic(topic, event)));
        return;
      case "invalidate":
        if (event.topic) await this.invalidateTopic(event.topic, event);
        return;
    }
  }

  private async invalidateTopic(topic: string, event: RealtimeEvent): Promise<void> {
    const keys = registries.get(kindOf(topic))?.(topic, event) ?? [];
    await Promise.all(keys.map((queryKey) => this.queryClient.invalidateQueries({ queryKey })));
  }

  /** A surface's `refetchInterval`: false while the stream is live, its poll otherwise (AC-T7). */
  interval(kind: PollKind): number | false {
    return this.polling ? POLL_MS[kind] : false;
  }
}

let shared: RealtimeClient | null = null;

/** The tab's one client (one stream per tab). */
export function realtimeClient(queryClient: QueryClient, open?: StreamOpener): RealtimeClient {
  shared ??= new RealtimeClient(queryClient, open);
  return shared;
}

/** For tests: forget the tab's client and the domain registries. */
export function resetRealtime(): void {
  shared?.stop();
  shared = null;
  registries.clear();
}
