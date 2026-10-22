import type { NotificationPageOut } from "@abacus/api-client";
import { type FixtureHandler, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../../fixtures/scenario";

// SHL-01 a–g (P-01 §5.3): Hannah Leclerc, any firm user, on Mon Sep 14, 2026 at 9:24 AM CT, over
// the Brightwater Hale seed. The toolbar reads one number of its own, `unread_count`: 4 in a (the
// dot) and 0 in d (no dot). The other states are where the toolbar is, not data: the 13 landing
// screens (b), the held states (c), the 1400 and 1279 widths (e), /settings/general (f) and the
// eight R2 screens (g). The drawer's rows arrive with P-01-T07; the toolbar never reads them.

const PERSONA = "hannah-leclerc";

function unread(count: number): FixtureHandler {
  const body: NotificationPageOut = { items: [], unread_count: count };
  return () => json(body);
}

function scenario(state: string, count: number) {
  const e0 = seedScenario();
  return {
    state,
    persona: PERSONA,
    ...(e0.clock === undefined ? {} : { clock: e0.clock }),
    handlers: { ...e0.handlers, "GET /v1/notifications": unread(count) },
  };
}

export const scenarios = defineScenarios({
  a: scenario("a", 4),
  b: scenario("b", 4),
  c: scenario("c", 4),
  d: scenario("d", 0),
  e: scenario("e", 4),
  f: scenario("f", 4),
  g: scenario("g", 4),
});

export type Shl01State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Shl01State[];
