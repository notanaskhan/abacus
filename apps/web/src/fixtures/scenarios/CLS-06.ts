// CLS-06 Close › Review's fixture scenarios (C-01-T39; handoff CLS-06): Copperleaf August at E0,
// seen by Raj Malhotra. a default (Sound Electric selected, register at check #2285), a2 the resolve
// dialog, b the ••4410 reconciliation for #2281, c Ben Ashby answered 1:12 PM, d resolved 1:20 PM
// (badge 6), e the Notes tab, f Show resolved, g empty. Data: seed/close-review.ts.
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { copperleafReconciliation } from "../seed/close-reconciliation";
import { type ReviewState, copperleafRegister4410, copperleafReview } from "../seed/close-review";
import { DEMO_INSTANT } from "../seed/clock";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();

function at(state: ReviewState): Scenario {
  const data: Record<string, FixtureHandler> = {
    "GET /v1/closes/{close_id}/issues": () => json(copperleafReview(state)),
    "GET /v1/closes/{close_id}/accounts/{account_ref}/register": ({ params }) =>
      params.account_ref === "35"
        ? json(copperleafRegister4410())
        : json({ detail: "not_found" }, 404),
    "GET /v1/closes/{close_id}/reconciliations/{account_ref}": ({ params }) =>
      params.account_ref === "35"
        ? json(copperleafReconciliation("a"))
        : json({ detail: "not_found" }, 404),
  };
  return {
    state,
    persona: "raj-malhotra",
    clock: DEMO_INSTANT,
    get handlers() {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona: who }: { persona?: string | undefined }) => {
          const base = capabilitiesFor(getSeed(), who ?? "raj-malhotra");
          return json({ ...base, flags: { ...base.flags, "closes.engine": true } });
        },
        ...data,
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a"),
  a2: at("a2"),
  b: at("b"),
  c: at("c"),
  d: at("d"),
  e: at("e"),
  f: at("f"),
  g: at("g"),
});

export type Cls06State = keyof typeof scenarios;

export interface Cls06Initial {
  selected?: "soundElectric" | "check2281";
  tab?: "exceptions" | "notes";
  register?: "detail" | "reconciliation";
  resolving?: boolean;
  answered?: boolean;
  showResolved?: boolean;
}

export const INITIAL: Record<Cls06State, Cls06Initial> = {
  a: {},
  a2: { resolving: true },
  b: { selected: "check2281", register: "reconciliation" },
  c: { answered: true },
  d: {},
  e: { tab: "notes" },
  f: { showResolved: true },
  g: {},
};
