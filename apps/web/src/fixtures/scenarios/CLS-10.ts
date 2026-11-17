// CLS-10 Flux's fixture scenarios (C-01-T40; handoff CLS-10): Copperleaf August against July at
// E0, seen by Priya Raman. a default (Payroll explained as a draft, Repairs unexplained), b 1:12 PM
// after Ben Ashby's answer (both explained), c 3:05 PM both accepted by Priya (the commentary
// banner), d year over year (dashes, not comparable), e the agent tracing Repairs. `raj` is a's
// data seen by Raj Malhotra (no `flux.accept`: Accept is absent). Data: seed/close-book.ts.
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { copperleafFluxAt } from "../seed/close-book";
import { DEMO_INSTANT } from "../seed/clock";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();

function at(
  state: string,
  persona: string,
  handlers: Record<string, FixtureHandler> = {},
): Scenario {
  const accept = persona === "priya-raman";
  return {
    state,
    persona,
    clock: DEMO_INSTANT,
    get handlers() {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona: who }: { persona?: string | undefined }) => {
          const base = capabilitiesFor(getSeed(), who ?? persona);
          return json({
            ...base,
            capabilities: [
              ...base.capabilities.filter((c: string) => c !== "flux.accept"),
              "flux.read",
              "flux.edit",
              "flux.explain",
              ...(accept ? ["flux.accept"] : []),
            ],
            flags: { ...base.flags, "closes.engine": true },
          });
        },
        ...handlers,
      };
    },
  };
}

const PR = "priya-raman";
const flux = (state: "a" | "b" | "c"): Record<string, FixtureHandler> => ({
  "GET /v1/closes/{close_id}/flux": ({ query }) =>
    (query.get("basis") ?? "mom") === "mom"
      ? json(copperleafFluxAt(state))
      : json({ detail: "not_found" }, 404),
});

export const scenarios = defineScenarios({
  a: at("a", PR),
  b: at("b", PR, flux("b")),
  c: at("c", PR, flux("c")),
  d: at("d", PR),
  e: at("e", PR),
  raj: at("raj", "raj-malhotra"),
});

export type FluxState = keyof typeof scenarios;

export interface FluxInitial {
  basis?: "mom" | "yoy";
  explaining?: string;
}

export const INITIAL: Record<FluxState, FluxInitial> = {
  a: {},
  b: {},
  c: {},
  d: { basis: "yoy" },
  e: { explaining: "repairs_maintenance" },
  raj: {},
};
