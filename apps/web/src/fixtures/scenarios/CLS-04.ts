// CLS-04 Close › Accounts' fixture scenarios (C-01-T37; handoff CLS-04): Copperleaf August at E0,
// seen by Raj Malhotra. a ties once posted (default), a2 the add-arrangement drawer, b approved
// 9:31 (read-only: no Post AJE), c′ recorded in QuickBooks (JE 48214 found by the 10:20 sync), d
// does not tie (off 60.00 to a review issue), e the Detail register, f the bank leaf selected
// (opens CLS-05). C-02-T56 adds C-02's W1 states: bpost (b with Post AJE), b2 (its confirm) and c
// (Posted · QBO 48214 · 10:20 AM). Data: seed/close-accounts.ts.
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  type AccountsState,
  PREPAID,
  copperleafAccountTree,
  copperleafPrepaidWorkpaper,
} from "../seed/close-accounts";
import { DEMO_INSTANT } from "../seed/clock";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();

function at(state: AccountsState): Scenario {
  const data: Record<string, FixtureHandler> = {
    "GET /v1/closes/{close_id}/accounts": () => json(copperleafAccountTree(state)),
    "GET /v1/closes/{close_id}/accounts/{account_ref}/workpaper": ({ params }) =>
      params.account_ref === PREPAID
        ? json(copperleafPrepaidWorkpaper(state))
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
          // C-02-T56: the W1 posting states run with `adjustments.posting` (Copperleaf is not
          // an attest client); b and c′ stay C-01's read-only variants (DV-1).
          const posting = state === "bpost" || state === "b2" || state === "c";
          return json({
            ...base,
            flags: { ...base.flags, "closes.engine": true, "adjustments.posting": posting },
          });
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
  bpost: at("bpost"),
  b2: at("b2"),
  c: at("c"),
  cprime: at("cprime"),
  d: at("d"),
  e: at("e"),
  f: at("f"),
});

export type Cls04State = keyof typeof scenarios;

export interface Cls04Initial {
  account?: string;
  view?: "detail" | "workpaper";
  arrangement?: boolean;
  /** C-02-T56 b2: the Post confirm open. */
  confirm?: boolean;
}

export const INITIAL: Record<Cls04State, Cls04Initial> = {
  a: {},
  a2: { arrangement: true },
  b: {},
  bpost: {},
  b2: { confirm: true },
  c: {},
  cprime: {},
  d: {},
  e: { view: "detail" },
  f: { account: "35" },
};
