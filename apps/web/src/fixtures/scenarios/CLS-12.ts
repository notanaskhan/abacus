// CLS-12 fixture scenarios (C-02-T15, DEC-5624; handoff CLS-12): the December 2026 close's tax hand-off, by Priya Raman.
// Each artboard's persona and clock (CDT until Sun Nov 1, 2026; CST after). Data handlers join
// with the screen task (fixtures from the Python scenario through `make fixtures`, never hand
// written); until then every state serves the E0 seed and the closes and posting flags on.
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();

function at(state: string, persona: string, clock: string): Scenario {
  return {
    state,
    persona,
    clock,
    get handlers() {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona: who }: { persona?: string | undefined }) => {
          const base = capabilitiesFor(getSeed(), who ?? persona);
          return json({
            ...base,
            flags: { ...base.flags, "closes.engine": true, "adjustments.posting": true },
          });
        },
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "priya-raman", "2027-01-12T14:15:00-06:00"),
  b: at("b", "priya-raman", "2026-09-14T09:24:00-05:00"),
  c: at("c", "priya-raman", "2027-01-12T14:15:00-06:00"),
  c2: at("c2", "priya-raman", "2027-01-12T14:15:00-06:00"),
  d: at("d", "priya-raman", "2027-01-20T09:24:00-06:00"),
});

export type Cls12State = keyof typeof scenarios;
export const INITIAL: Cls12State = "a";
