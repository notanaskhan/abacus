// SHL-02 "Go…" palette: one fixture scenario per artboard (P-02-T11; docs/screens/SHL-02.md), seen
// by Hannah Leclerc. a–e at E0 (Mon Sep 14, 2026 9:24 AM CT), f–g on Mon Sep 28, 2026 9:10 AM CT:
//
//   a  "feld": Clients, Returns (the 1065 by its partner), Binders, Files, Inbox, Actions
//   b  nothing typed: Recent (5) and Create (7)
//   c  ">" with `search.agent_mode` on: Run an agent (6)
//   d  "pellstret": the empty state and one visible-only suggestion
//   e  "feld" with a wall on two Feld documents: a without them, no note and no count (DEC-43)
//   f  "granite": Clients, Audits, To-dos
//   g  "explain": Saved prompts (deferred to W-03; gallery only)
//   loading, error: the search never answers; 503 `search_unavailable`
//
// Dev and test only.
import type { CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
  never,
} from "../../app-core/fixture-mode";
import { searchHandlers } from "../handlers/search";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { capabilitiesFor } from "../seed/shell";
import { SHL02_CLOCK, SHL02_SEP28 } from "../seed/shl02";

const E0 = seedScenario();
const seed = getSeed();
export const SHL02_PERSONA = "hannah-leclerc";

function capabilities(agentMode: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, SHL02_PERSONA);
  return {
    ...base,
    flags: { ...base.flags, "search.palette": true, "search.agent_mode": agentMode },
  };
}

function at(
  state: string,
  clock: string,
  handlers: Record<string, FixtureHandler> = {},
  agentMode = false,
): Scenario {
  return {
    state,
    persona: SHL02_PERSONA,
    clock,
    handlers: {
      ...E0.handlers,
      ...searchHandlers(),
      "GET /v1/me/capabilities": () => json(capabilities(agentMode)),
      ...handlers,
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", SHL02_CLOCK),
  b: at("b", SHL02_CLOCK),
  c: at("c", SHL02_CLOCK, {}, true),
  d: at("d", SHL02_CLOCK),
  e: at("e", SHL02_CLOCK, searchHandlers(true)),
  f: at("f", SHL02_SEP28),
  g: at("g", SHL02_SEP28),
  loading: at("loading", SHL02_CLOCK, { "POST /v1/search": () => never() }),
  error: at("error", SHL02_CLOCK, {
    "POST /v1/search": () =>
      json({ code: "search_unavailable", detail: "search_unavailable" }, 503),
  }),
});

export type Shl02State = keyof typeof scenarios;

/** The text each state's palette opens with. */
export const QUERIES: Readonly<Record<Shl02State, string>> = {
  a: "feld",
  b: "",
  c: ">",
  d: "pellstret",
  e: "feld",
  f: "granite",
  g: "explain",
  loading: "feld",
  error: "feld",
};
