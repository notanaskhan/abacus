// P-10-T30 (TASK-6608): the real-time client. Row acceptance: "In Vitest a scripted invalidate
// refetches only matching query keys, three failures switch to refetchInterval, and locked clears
// the cache and shows the not-allowed state."

import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it } from "vitest";
import {
  MAX_FAILURES,
  POLL_MS,
  type RealtimeEvent,
  RealtimeClient,
  registerTopicKeys,
  resetRealtime,
  type StreamOpener,
} from "./realtime";

const NORTHWIND = "6f1c2c4e-0000-4000-8000-000000000001";
const GRANITE = "6f1c2c4e-0000-4000-8000-000000000002";

async function* replay(events: RealtimeEvent[]): AsyncGenerator<RealtimeEvent> {
  for (const event of events) yield await Promise.resolve(event);
}

function scripted(events: RealtimeEvent[], failures = 0): StreamOpener {
  return ({ onError }) => {
    for (let n = 0; n < failures; n += 1) onError(new Error("closed"));
    return replay(events);
  };
}

function seeded(): QueryClient {
  const queries = new QueryClient();
  queries.setQueryData(["engagements", NORTHWIND], { id: NORTHWIND });
  queries.setQueryData(["engagements", GRANITE], { id: GRANITE });
  queries.setQueryData(["notifications"], []);
  return queries;
}

const invalidated = (queries: QueryClient, key: readonly unknown[]): boolean =>
  queries.getQueryState(key)?.isInvalidated ?? false;

afterEach(() => {
  resetRealtime();
});

describe("the real-time client", () => {
  it("refetches only the query keys an invalidate's topic maps to", async () => {
    registerTopicKeys("engagement", (topic) => [["engagements", topic.split(":")[1]]]);
    const queries = seeded();
    const event: RealtimeEvent = {
      seq: 18343,
      type: "invalidate",
      topic: `engagement:${NORTHWIND}`,
    };
    const live = new RealtimeClient(queries, scripted([{ seq: 18342, type: "stream" }, event]));
    await live.start([`engagement:${NORTHWIND}`, `engagement:${GRANITE}`]);
    expect(invalidated(queries, ["engagements", NORTHWIND])).toBe(true);
    expect(invalidated(queries, ["engagements", GRANITE])).toBe(false);
    expect(invalidated(queries, ["notifications"])).toBe(false);
  });

  it("refreshes the bell on a notice", async () => {
    const queries = seeded();
    const live = new RealtimeClient(
      queries,
      scripted([{ seq: 1, type: "notice", topic: "user:me" }]),
    );
    await live.start(["user:me"]);
    expect(invalidated(queries, ["notifications"])).toBe(true);
  });

  it("switches every surface to polling after three failures", async () => {
    const queries = seeded();
    const live = new RealtimeClient(queries, scripted([], MAX_FAILURES));
    expect(live.interval("record")).toBe(POLL_MS.record); // off: it polls before connecting
    await live.start([`engagement:${NORTHWIND}`]);
    expect(live.state).toBe("polling");
    expect(live.interval("record")).toBe(5_000);
    expect(live.interval("list")).toBe(30_000);
    expect(live.interval("bell")).toBe(60_000);
  });

  it("is live with no polling while the stream delivers", async () => {
    const queries = seeded();
    let seen: number | false = 0;
    async function* stream(): AsyncGenerator<RealtimeEvent> {
      yield await Promise.resolve<RealtimeEvent>({ seq: 1, type: "stream" });
      seen = live.interval("record");
    }
    const opener: StreamOpener = () => stream();
    const live = new RealtimeClient(queries, opener);
    await live.start(["user:me"]);
    expect(seen).toBe(false);
  });

  it("clears the cache on locked and shows the not-allowed state", async () => {
    const queries = seeded();
    const states: string[] = [];
    const live = new RealtimeClient(
      queries,
      scripted([{ seq: 7, type: "locked", topic: `engagement:${NORTHWIND}` }]),
    );
    live.subscribe((s) => states.push(s));
    await live.start([`engagement:${NORTHWIND}`]);
    expect(queries.getQueryData(["engagements", NORTHWIND])).toBeUndefined();
    expect(queries.getQueryData(["engagements", GRANITE])).toBeUndefined();
    expect(live.state).toBe("locked");
    expect(states).toContain("locked");
  });

  it("refetches every registered topic on resync", async () => {
    registerTopicKeys("engagement", (topic) => [["engagements", topic.split(":")[1]]]);
    const queries = seeded();
    const live = new RealtimeClient(queries, scripted([{ seq: 9, type: "resync" }]));
    await live.start([`engagement:${NORTHWIND}`, `engagement:${GRANITE}`]);
    expect(invalidated(queries, ["engagements", NORTHWIND])).toBe(true);
    expect(invalidated(queries, ["engagements", GRANITE])).toBe(true);
  });
});

// TASK-7325: one stream per tab carries every mounted surface's topics.
describe("the tab's topics are the union of its surfaces'", () => {
  function recording(): { opener: StreamOpener; opened: string[][]; aborted: boolean[] } {
    const opened: string[][] = [];
    const aborted: boolean[] = [];
    const opener: StreamOpener = ({ topics, signal }) => {
      const index = opened.length;
      opened.push([...topics]);
      aborted.push(false);
      signal.addEventListener("abort", () => {
        aborted[index] = true;
      });
      return (async function* (): AsyncGenerator<RealtimeEvent> {
        // Open until aborted: a live stream that sends nothing.
        await new Promise<void>((resolve) => {
          signal.addEventListener("abort", () => {
            resolve();
          });
        });
        yield* [];
      })();
    };
    return { opener, opened, aborted };
  }

  it("a drawer adds its topic beside the page's, and leaving removes only its own", () => {
    const { opener, opened, aborted } = recording();
    const live = new RealtimeClient(new QueryClient(), opener);
    const page = Symbol("page");
    const drawer = Symbol("drawer");
    live.want(page, [`engagement:${NORTHWIND}`]);
    live.want(drawer, ["session:s1"]);
    expect(opened).toEqual([
      [`engagement:${NORTHWIND}`],
      [`engagement:${NORTHWIND}`, "session:s1"],
    ]);
    live.unwant(drawer);
    expect(opened.at(-1)).toEqual([`engagement:${NORTHWIND}`]);
    expect(live.state).toBe("connecting");
    live.unwant(page);
    expect(aborted.every(Boolean)).toBe(true);
    expect(live.state).toBe("off");
  });

  it("the same union reopens nothing", () => {
    const { opener, opened } = recording();
    const live = new RealtimeClient(new QueryClient(), opener);
    live.want(Symbol("a"), ["user:me"]);
    live.want(Symbol("b"), ["user:me"]);
    expect(opened).toHaveLength(1);
  });
});
