// Presence sources (C-28; F-08-T24; DEC-5932): where heartbeats come from. The kit never fetches
// on its own: the host passes a source built on its generated client or its SSE connection
// (P-10's `presence:{object_ref}` topic, identifiers only), and specimens pass a scripted one.
//   - PollingPresenceSource: calls the host's read every `intervalMs` (15 s, the heartbeat).
//   - SsePresenceSource: adapts the host's event subscription (one event per heartbeat or leave).
//   - ScriptedPresenceSource: replays frames on a clock; under `?static=1` it emits the last
//     frame at once and stops (parity screenshots never move).
import type { PresenceHeartbeat } from "./store";

export type PresenceEvent =
  { kind: "beat"; beat: PresenceHeartbeat } | { kind: "leave"; userId: string };

export interface PresenceSource {
  /** Start delivering events; the returned function stops it. */
  subscribe(onEvent: (event: PresenceEvent) => void): () => void;
}

export const HEARTBEAT_MS = 15_000;

export class PollingPresenceSource implements PresenceSource {
  constructor(
    private readonly read: () => Promise<readonly PresenceHeartbeat[]>,
    private readonly intervalMs: number = HEARTBEAT_MS,
  ) {}

  subscribe(onEvent: (event: PresenceEvent) => void): () => void {
    let stopped = false;
    const tick = async (): Promise<void> => {
      try {
        for (const beat of await this.read()) if (!stopped) onEvent({ kind: "beat", beat });
      } catch {
        // A failed poll shows no one new; the TTL drops the stale ones.
      }
    };
    void tick();
    const id = setInterval(() => void tick(), this.intervalMs);
    return () => {
      stopped = true;
      clearInterval(id);
    };
  }
}

/** The host's subscription to the SSE topic, adapted: `listen` returns its own unsubscribe. */
export class SsePresenceSource implements PresenceSource {
  constructor(private readonly listen: (onEvent: (event: PresenceEvent) => void) => () => void) {}

  subscribe(onEvent: (event: PresenceEvent) => void): () => void {
    return this.listen(onEvent);
  }
}

export interface ScriptedFrame {
  /** When the frame plays, in ms after subscribe. */
  afterMs: number;
  events: readonly PresenceEvent[];
}

export class ScriptedPresenceSource implements PresenceSource {
  constructor(
    private readonly frames: readonly ScriptedFrame[],
    private readonly options: { static?: boolean } = {},
  ) {}

  subscribe(onEvent: (event: PresenceEvent) => void): () => void {
    if (this.options.static === true) {
      for (const frame of this.frames) for (const e of frame.events) onEvent(e);
      return () => undefined;
    }
    const timers = this.frames.map((frame) =>
      setTimeout(() => {
        for (const e of frame.events) onEvent(e);
      }, frame.afterMs),
    );
    return () => {
      for (const t of timers) clearTimeout(t);
    };
  }
}
