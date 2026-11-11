// A-07-T47 (TASK-6737): the live completion hooks' rules: 10 s polling (2 s while a workflow runs),
// invalidation of exactly the completion reads, and refusals in words.
import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { aud24, aud25 } from "../../fixtures/seed/audit-completion";
import {
  COMPLETION_QUERIES,
  LIVE_POLL_MS,
  REFUSAL_PROBLEM,
  RUN_POLL_MS,
  asksForStepUp,
  invalidateCompletion,
  lockRunning,
  refusalWords,
  releaseRunning,
} from "./completionLive";

describe("A-07-T47 live completion", () => {
  it("polls every 10 s, every 2 s while a run is open", () => {
    expect(LIVE_POLL_MS).toBe(10_000);
    expect(RUN_POLL_MS).toBe(2_000);
    expect(releaseRunning(true, aud24("a"))).toBe(true);
    expect(releaseRunning(true, aud24("d"))).toBe(false);
    expect(releaseRunning(false, aud24("a"))).toBe(false);
    expect(lockRunning(true, aud25("b"))).toBe(true);
    expect(lockRunning(true, aud25("c"))).toBe(false);
    expect(lockRunning(false, { ...aud25("b"), status: "locking" })).toBe(true);
  });

  it("refuses in words, never the raw code; mfa_required asks for the step-up", () => {
    for (const code of ["archived", "gates_not_met", "content_changed", "mfa_required"]) {
      const words = refusalWords({ detail: code });
      expect(words).not.toBe(REFUSAL_PROBLEM);
      expect(words).not.toContain("_"); // a sentence, never the server's code
    }
    expect(refusalWords({ detail: "something_new" })).toBe(REFUSAL_PROBLEM);
    expect(refusalWords(null)).toBe(REFUSAL_PROBLEM);
    expect(asksForStepUp({ detail: "mfa_required" })).toBe(true);
    expect(asksForStepUp({ facts: { reason: "mfa_required" } })).toBe(true);
    expect(asksForStepUp({ detail: "gates_not_met" })).toBe(false);
  });

  it("a mutation invalidates the completion reads and nothing else", async () => {
    const client = new QueryClient();
    const key = (id: string) => [{ _id: id }];
    for (const id of [...COMPLETION_QUERIES, "listClients"]) client.setQueryData(key(id), 1);
    await invalidateCompletion(client);
    for (const id of COMPLETION_QUERIES) {
      expect(client.getQueryState(key(id))?.isInvalidated).toBe(true);
    }
    expect(client.getQueryState(key("listClients"))?.isInvalidated).toBe(false);
  });
});
