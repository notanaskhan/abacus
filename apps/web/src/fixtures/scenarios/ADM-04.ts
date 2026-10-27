// ADM-04 AI policy & approval gates: one fixture scenario per artboard the AI-policy contract
// serves (G-02-T15; G-02 §5.4; docs/screens/ADM-04.md). a, b, d, h, i and j are Margaret
// Okonkwo (QM owner) at E0, Mon Sep 14, 2026, 9:24 AM CT; e is Hannah Leclerc, read-only; g is
// the next morning, v4 effective Sep 15. T03's frames: `band` (Grace Holloway: the client-data
// opt-in, agent stages, Pause all agents), `awaiting` (Daniel Reyes: "Awaiting approval · Daniel
// Reyes") and `real_firm` (Auto mode off and locked). c and f (the dormant policy principal,
// fixture-only) arrive with the screen (G-02-T25); k is I-03-T37's.

import { defineScenarios } from "../../app-core/fixture-mode";
import { type AiPolicyOptions, aiPolicyHandlers } from "../handlers/ai-policy";
import { seedScenario } from "../scenario";
import { AI_POLICY_E0, AI_POLICY_G } from "../seed/ai-policy";

const E0 = seedScenario();

function at(state: string, persona: string, options: AiPolicyOptions = {}, clock = AI_POLICY_E0) {
  return {
    state,
    persona,
    clock,
    handlers: { ...E0.handlers, ...aiPolicyHandlers(options) },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "margaret-okonkwo"),
  b: at("b", "margaret-okonkwo", { view: "b" }),
  d: at("d", "margaret-okonkwo", { view: "b" }),
  e: at("e", "hannah-leclerc", { view: "read_only" }),
  g: at("g", "margaret-okonkwo", { view: "g" }, AI_POLICY_G),
  h: at("h", "margaret-okonkwo"),
  i: at("i", "margaret-okonkwo"),
  j: at("j", "margaret-okonkwo"),
  band: at("band", "grace-holloway", { view: "band" }),
  awaiting: at("awaiting", "daniel-reyes", { view: "awaiting" }),
  real_firm: at("real_firm", "margaret-okonkwo", { view: "real_firm" }),
});

export type Adm04State = keyof typeof scenarios;
