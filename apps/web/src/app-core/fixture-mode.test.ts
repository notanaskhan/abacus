// F-04-T04: fixture mode answers the generated client from a scenario, by OpenAPI path, with the
// scenario's persona and clock; unknown routes are 404 and the real fetch comes back after.
import { client } from "@abacus/api-client/client";
import { afterEach, describe, expect, it } from "vitest";
import { nowMs } from "./clock";
import { defineScenarios, installFixtureMode, json, never } from "./fixture-mode";

let restore: (() => void) | null = null;
afterEach(() => {
  restore?.();
  restore = null;
});

const scenarios = defineScenarios({
  a: {
    state: "a",
    persona: "hannah-leclerc",
    clock: "2026-09-14T09:41:00-05:00",
    handlers: {
      "GET /v1/engagements/{engagement_id}": ({ params, persona }) =>
        json({ id: params.engagement_id, seenAs: persona }),
      "GET /v1/engagements": () => never(),
    },
  },
});

describe("fixture mode", () => {
  it("answers by OpenAPI path with the persona, and stands the clock at the scenario", async () => {
    restore = installFixtureMode(scenarios.a);
    const fetcher = client.getConfig().fetch as (r: Request) => Promise<Response>;
    const response = await fetcher(new Request("http://x/v1/engagements/e-42"));
    expect(await response.json()).toEqual({ id: "e-42", seenAs: "hannah-leclerc" });
    expect(nowMs()).toBe(Date.parse("2026-09-14T09:41:00-05:00"));
    const missing = await fetcher(new Request("http://x/v1/clients", { method: "GET" }));
    expect(missing.status).toBe(404);
  });

  it("restores the real fetch and clock", () => {
    const before = client.getConfig().fetch;
    installFixtureMode(scenarios.a)();
    expect(client.getConfig().fetch).toBe(before);
    expect(Math.abs(nowMs() - Date.now())).toBeLessThan(1_000);
  });

  it("refuses a scenario whose key and state differ or whose route isn't an API path", () => {
    expect(() => defineScenarios({ b: { state: "c", handlers: {} } })).toThrow(/state/);
    expect(() =>
      defineScenarios({ a: { state: "a", handlers: { "GET /health": () => json({}) } } }),
    ).toThrow(/METHOD/);
  });
});
