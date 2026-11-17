// CLS-05 Close › Reconciliation's fixture scenarios (C-01-T38; handoff CLS-05): Operating Checking
// ••4410 at Aug 31, seen by Raj Malhotra. a difference $0.00 with 2 open items (default), a2 the
// Propose AJE drawer, a3 sign-off blocked, b Run 1 off 380.00, c AJE-06 proposed, d reconciled and
// signed (read-only, recorded in QuickBooks), e loading pages, f Detail, g Savings ••4436 with its
// statement still requested. Data: seed/close-reconciliation.ts.
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { ACCOUNT_4436 } from "../seed/close-accounts";
import {
  type ReconciliationState,
  copperleafReconciliation,
  copperleafRegister4410,
  copperleafSavings4436,
} from "../seed/close-reconciliation";
import { DEMO_INSTANT } from "../seed/clock";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();

function at(state: ReconciliationState): Scenario {
  const data: Record<string, FixtureHandler> = {
    "GET /v1/closes/{close_id}/reconciliations/{account_ref}": ({ params }) =>
      params.account_ref === ACCOUNT_4436
        ? json(copperleafSavings4436())
        : params.account_ref === "35"
          ? json(copperleafReconciliation(state))
          : json({ detail: "not_found" }, 404),
    "GET /v1/closes/{close_id}/accounts/{account_ref}/register": ({ params }) =>
      params.account_ref === "35"
        ? json(copperleafRegister4410())
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
  a3: at("a3"),
  b: at("b"),
  c: at("c"),
  d: at("d"),
  e: at("e"),
  f: at("f"),
  g: at("g"),
});

export type Cls05State = keyof typeof scenarios;

export interface Cls05Initial {
  account?: string;
  view?: "detail" | "reconciliation";
  propose?: boolean;
  signOff?: boolean;
  loadingPages?: boolean;
}

export const INITIAL: Record<Cls05State, Cls05Initial> = {
  a: {},
  a2: { propose: true },
  a3: { signOff: true },
  b: {},
  c: {},
  d: {},
  e: { loadingPages: true },
  f: { view: "detail" },
  g: { account: ACCOUNT_4436 },
};
