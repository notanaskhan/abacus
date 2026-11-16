// TXT-02 Review › Trust Calculation's scenarios (T-07-T17): the Calloway 2025 Form 1041 at E0
// (Samuel Ito). a default (Nora's DNI allocated lit), a2 a with SHL-12 L2 open (the route's
// overlay), b collapsed overview, c by character, d Changed (Theo Dec 15 80,000 → 100,000), e
// signed off, f1 waiting on interpretation (409 interpretation_not_approved), loading and error.
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { DEMO_INSTANT } from "../seed/clock";
import { type CalcState, callowayComputation } from "../seed/fiduciary-calc";
import { capabilitiesFor } from "../seed/shell";
import { CALLOWAY_RETURN } from "./TXT-01";

const E0 = seedScenario();

function at(state: string, answer: () => Response | ReturnType<typeof json>): Scenario {
  return {
    state,
    persona: "samuel-ito",
    clock: DEMO_INSTANT,
    get handlers() {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona: who }: { persona?: string | undefined }) => {
          const base = capabilitiesFor(getSeed(), who ?? "samuel-ito");
          return json({ ...base, flags: { ...base.flags, "tax.fiduciary_workpapers": true } });
        },
        "GET /v1/tax/returns/{return_id}/fiduciary-computation": answer,
      };
    },
  };
}

const ok = (s: CalcState) => () => json(callowayComputation(CALLOWAY_RETURN, s));

export const scenarios = defineScenarios({
  a: at("a", ok("base")),
  a2: at("a2", ok("base")),
  b: at("b", ok("base")),
  c: at("c", ok("base")),
  d: at("d", ok("changed")),
  e: at("e", ok("signed")),
  f1: at("f1", () => json({ code: "interpretation_not_approved", detail: "interpretation_not_approved" }, 409)),
  error: at("error", () => json({ detail: "internal" }, 500)),
});

export type CalcScenario = keyof typeof scenarios;
