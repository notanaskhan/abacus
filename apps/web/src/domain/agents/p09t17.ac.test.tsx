// ac-test-author: notanaskhan
// P-09-T17 (TASK-6622; ADR-078 independent; SPEC-648): the AC tests for P-09's amber engines
// (P-09-T05 RunStore and polling, P-09-T06 AgentBlocks, P-09-T14 attribution), written from the
// P-09 epic and the row, not from the engines' tests. Row acceptance: "The tests merge green and
// fail under a seeded mutation of each rule." Each rule is a check over an implementation; the
// suite runs it on the real one (passes) and on a seeded mutant (must fail), so a check that
// cannot tell them apart fails here.
import type { AgentRunOut, RunItemOut, RunItemsOut } from "@abacus/api-client";
import {
  type Actor,
  AgentBlocks,
  type AgentBlocksPayload,
  HumanAction,
  formatActor,
} from "@abacus/ui";
import { cleanup, render } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { applyItems, EMPTY_FEED, type RunFeed } from "./feedCore";
import { PollingRunSource, RunStore, type Visibility } from "./runSource";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const RUN: AgentRunOut = {
  id: "00000000-0000-4000-8000-000000004118",
  agent: "close_review",
  agent_label: "Copperleaf August 2026 close review",
  state: "running",
  started_at: "2026-09-14T14:24:00Z",
  finished_at: null,
  duration_ms: null,
  initiator_name: "Priya Raman",
  subject: null,
};

function item(seq: number, code = `step.${String(seq)}`): RunItemOut {
  return {
    seq,
    kind: "tool_card",
    code,
    actor: null,
    at: "2026-09-14T14:24:00Z",
    detail: null,
    outcome: null,
    ref_id: null,
    ref_type: null,
  };
}

function page(seqs: number[], over: Partial<RunItemsOut> = {}): RunItemsOut {
  return {
    items: seqs.map((s) => item(s)),
    last_seq: Math.max(0, ...seqs),
    resync: false,
    run: RUN,
    ...over,
  };
}

/** A check passes silently or throws; `bites` proves the mutant breaks it. */
function bites(check: () => void): void {
  expect(check).toThrow();
}

// --- RunStore: ordering and duplicate seq ---------------------------------------------------

type Apply = (feed: RunFeed, p: RunItemsOut) => RunFeed;

function orderingCheck(apply: Apply): void {
  let feed = apply(EMPTY_FEED, page([3, 1]));
  feed = apply(feed, page([2]));
  expect(feed.items.map((i) => i.seq)).toEqual([1, 2, 3]);
}

function duplicateCheck(apply: Apply): void {
  let feed = apply(EMPTY_FEED, page([1, 2]));
  feed = apply(feed, { ...page([2, 3]), items: [item(2, "changed"), item(3)] });
  expect(feed.items.map((i) => i.seq)).toEqual([1, 2, 3]);
  expect(feed.items.find((i) => i.seq === 2)?.code).toBe("step.2"); // applied once, not twice
}

function resyncCheck(apply: Apply): void {
  let feed = apply(EMPTY_FEED, page([1, 2, 3]));
  feed = apply(feed, page([7], { resync: true, last_seq: 7 }));
  expect(feed.items.map((i) => i.seq)).toEqual([7]);
  expect(feed.lastSeq).toBe(7);
}

const unordered: Apply = (feed, p) => ({
  run: p.run,
  items: [...feed.items, ...p.items.filter((i) => !feed.items.some((f) => f.seq === i.seq))],
  lastSeq: Math.max(feed.lastSeq, p.last_seq),
});
const duplicating: Apply = (feed, p) => ({
  run: p.run,
  items: [...feed.items, ...p.items].sort((a, b) => a.seq - b.seq),
  lastSeq: Math.max(feed.lastSeq, p.last_seq),
});
const ignoringResync: Apply = (feed, p) => {
  const seen = new Set(feed.items.map((i) => i.seq));
  const items = [...feed.items, ...p.items.filter((i) => !seen.has(i.seq))];
  return { run: p.run, items: items.sort((a, b) => a.seq - b.seq), lastSeq: p.last_seq };
};

describe("RunStore ordering and duplicate seq (P-09-T05)", () => {
  it("items read in seq order whatever order the pages bring them", () => {
    orderingCheck(applyItems);
    bites(() => {
      orderingCheck(unordered);
    });
  });

  it("a seq seen twice is applied once", () => {
    duplicateCheck(applyItems);
    bites(() => {
      duplicateCheck(duplicating);
    });
  });

  it("resync replaces the feed", () => {
    resyncCheck(applyItems);
    bites(() => {
      resyncCheck(ignoringResync);
    });
  });

  it("the store hands every reader one snapshot per page, in order", () => {
    const store = new RunStore();
    const seen: number[][] = [];
    store.subscribe(() => {
      seen.push(store.getSnapshot().items.map((i) => i.seq));
    });
    store.apply(page([2]));
    store.apply(page([1, 2]));
    expect(seen).toEqual([[2], [1, 2]]);
  });
});

// --- polling stop rules -------------------------------------------------------------------------

function visibility(hidden: { value: boolean }): Visibility & { fire: () => void } {
  let listener: (() => void) | null = null;
  return {
    hidden: () => hidden.value,
    onChange: (l) => {
      listener = l;
      return () => {
        listener = null;
      };
    },
    fire: () => {
      listener?.();
    },
  };
}

async function flush(): Promise<void> {
  for (let i = 0; i < 5; i += 1) await Promise.resolve();
}

describe("polling stop rules (P-09-T05)", () => {
  it("a terminal state stops polling for good", async () => {
    vi.useFakeTimers();
    const states: AgentRunOut["state"][] = ["running", "succeeded", "running"];
    const fetchPage = vi.fn((after: number) => {
      const state = states[Math.min(fetchPage.mock.calls.length - 1, 2)] ?? "running";
      return Promise.resolve(page([after + 1], { run: { ...RUN, state } }));
    });
    const source = new PollingRunSource(fetchPage, {
      intervalMs: 1500,
      visibility: visibility({ value: false }),
    });
    source.start();
    await flush();
    await vi.advanceTimersByTimeAsync(1500);
    await flush();
    expect(fetchPage).toHaveBeenCalledTimes(2); // running, then succeeded
    await vi.advanceTimersByTimeAsync(15_000);
    expect(fetchPage).toHaveBeenCalledTimes(2);
    source.start(); // a stopped source never restarts
    await vi.advanceTimersByTimeAsync(15_000);
    expect(fetchPage).toHaveBeenCalledTimes(2);
  });

  it("needs_input and failed are terminal too; queued keeps polling", async () => {
    vi.useFakeTimers();
    for (const [state, calls] of [
      ["needs_input", 1],
      ["failed", 1],
      ["queued", 3],
    ] as const) {
      const fetchPage = vi.fn(() => Promise.resolve(page([1], { run: { ...RUN, state } })));
      const source = new PollingRunSource(fetchPage, {
        intervalMs: 1000,
        visibility: visibility({ value: false }),
      });
      source.start();
      await flush();
      await vi.advanceTimersByTimeAsync(2000);
      expect(fetchPage, state).toHaveBeenCalledTimes(calls);
      source.stop();
    }
  });

  it("a hidden tab does not poll, and visibility resumes it", async () => {
    vi.useFakeTimers();
    const hidden = { value: true };
    const vis = visibility(hidden);
    const fetchPage = vi.fn(() => Promise.resolve(page([1])));
    const source = new PollingRunSource(fetchPage, { intervalMs: 1000, visibility: vis });
    source.start();
    await vi.advanceTimersByTimeAsync(5000);
    expect(fetchPage).not.toHaveBeenCalled();
    hidden.value = false;
    vis.fire();
    await flush();
    expect(fetchPage).toHaveBeenCalledTimes(1);
    source.stop();
  });

  it("stop() while a request is in flight drops its page", async () => {
    let resolve: (p: RunItemsOut) => void = () => undefined;
    const fetchPage = vi.fn(
      () =>
        new Promise<RunItemsOut>((r) => {
          resolve = r;
        }),
    );
    const source = new PollingRunSource(fetchPage, { visibility: visibility({ value: false }) });
    const pages: RunItemsOut[] = [];
    source.subscribe((e) => {
      if (e.kind === "page") pages.push(e.page);
    });
    source.start();
    source.stop();
    resolve(page([1]));
    await flush();
    expect(pages).toEqual([]);
  });

  it("the after_seq cursor moves with the last seq seen", async () => {
    vi.useFakeTimers();
    const fetchPage = vi.fn((after: number) => Promise.resolve(page([after + 1, after + 2])));
    const source = new PollingRunSource(fetchPage, {
      intervalMs: 100,
      visibility: visibility({ value: false }),
    });
    source.start();
    await flush();
    await vi.advanceTimersByTimeAsync(100);
    await flush();
    expect(fetchPage.mock.calls.map((c) => c[0])).toEqual([0, 2]);
    source.stop();
  });
});

// --- AgentBlocks never renders raw payload or HTML ---------------------------------------------

const HOSTILE = '<img src=x onerror="alert(1)"><script>alert(2)</script>';

function renderBlocks(Renderer: (props: { blocks: AgentBlocksPayload }) => JSX.Element): string {
  const { container } = render(
    <Renderer
      blocks={{
        parts: [
          { kind: "p", segments: [{ kind: "text", text: HOSTILE }] },
          { kind: "unknown_part", payload: "raw-payload-1234" } as { kind: string },
          { kind: "metric", label: "Net effect", fact_id: "missing-fact-id" },
        ],
      }}
    />,
  );
  const html = container.innerHTML;
  cleanup();
  return html;
}

function blocksCheck(html: string): void {
  expect(html).not.toMatch(/<img|<script/i); // markup is text, never elements
  expect(html).not.toContain("raw-payload-1234"); // an unknown part shows no payload
  expect(html).not.toContain("missing-fact-id"); // an unknown fact shows a dash, never its id
}

/** A mutant that renders the payload as markup and dumps unknown parts. */
function RawBlocks({ blocks }: { blocks: AgentBlocksPayload }): JSX.Element {
  return (
    <div
      dangerouslySetInnerHTML={{
        __html: blocks.parts
          .map((p) =>
            p.kind === "p" && "segments" in p
              ? p.segments.map((s) => (s.kind === "text" ? s.text : "")).join("")
              : JSON.stringify(p),
          )
          .join(""),
      }}
    />
  );
}

describe("AgentBlocks never renders raw payload or HTML (P-09-T06)", () => {
  it("hostile text, an unknown part and an unknown fact render safely", () => {
    blocksCheck(renderBlocks(({ blocks }) => <AgentBlocks blocks={blocks} facts={{}} />));
    bites(() => {
      blocksCheck(renderBlocks(RawBlocks));
    });
  });
});

// --- HumanAction refuses agent actors; formatActor --------------------------------------------

const NOT_PEOPLE: Actor[] = [
  { kind: "agent" },
  { kind: "agent_assisted", person: "Hannah Leclerc" },
  { kind: "policy", name: "BH AJE thresholds", version: 2 },
  { kind: "system" },
];

function humanActionCheck(Control: typeof HumanAction): void {
  for (const actor of NOT_PEOPLE) {
    const { container } = render(<Control verb="Approve" object="Document" actor={actor} />);
    expect(container.querySelector("button"), actor.kind).toBeNull();
    cleanup();
  }
  const { getByRole } = render(
    <Control verb="Approve" object="Document" actor={{ kind: "human", name: "Priya Raman" }} />,
  );
  expect(getByRole("button", { name: "Approve Document" })).toBeTruthy();
  cleanup();
}

/** A mutant that lets any actor carry the verb. */
const AnyActorAction = ((props: Parameters<typeof HumanAction>[0]) => (
  <button type="button">{`${props.verb} ${props.object ?? ""}`.trim()}</button>
)) as typeof HumanAction;

function actorCheck(format: typeof formatActor): void {
  expect(format({ kind: "policy", name: "BH AJE thresholds", version: 2 })).toBe(
    "Policy: BH AJE thresholds v2",
  );
  // A person's approval with the agent's help is the person's, never the agent's.
  const assisted = format({ kind: "agent_assisted", person: "Raj Malhotra" });
  expect(assisted).toBe("Raj Malhotra via Agent");
  expect(assisted).not.toContain("Accrued Agent");
  expect(format({ kind: "human", name: " Priya Raman " })).toBe("Priya Raman");
}

const agentNamingFormat: typeof formatActor = (actor) =>
  actor.kind === "agent_assisted" ? "Accrued Agent" : formatActor(actor);
const policyWithoutVersion: typeof formatActor = (actor) =>
  actor.kind === "policy" ? `Policy: ${actor.name}` : formatActor(actor);

describe("attribution (P-09-T14)", () => {
  it("HumanAction renders nothing for the agent, a policy or the system", () => {
    humanActionCheck(HumanAction);
    bites(() => {
      humanActionCheck(AnyActorAction);
    });
  });

  it("formatActor reads 'Policy: BH AJE thresholds v2' and never 'Accrued Agent' for an approval", () => {
    actorCheck(formatActor);
    bites(() => {
      actorCheck(agentNamingFormat);
    });
    bites(() => {
      actorCheck(policyWithoutVersion);
    });
  });
});
