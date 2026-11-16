// AUD-32 Consolidation setup (A-09-T14; SPEC-658 AC-1.1 to AC-1.3; handoff AUD-32 spec.md): one
// fixture scenario per state, Omar Haddad on Harlow & Pike FY2026 (A28), read through C9 v2.1's
// shapes (seed/group-audit.ts):
//
//   a  10:44 AM  Trial balances: 9 of 10 attached, missing H&P Real Estate · Prior (default)
//   b  10:31 AM  Details
//   c  10:36 AM  Structure: the proposed three tiers, before any TB
//   d  10:47 AM  Review: 10 attached (Real Estate Prior marked not needed), 187,860,000
//   e  10:48 AM  Finalized
//   f  10:44 AM  Pull failed: Distribution interim needs reauth
//
// Marking a slot not needed moves a to d; Finalize moves d to e. Dev and test only.

import type {
  ConsolidationEntityOut,
  ConsolidationOut,
  TrialBalanceSlotOut,
} from "@abacus/api-client";
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { CONSOLIDATION_REVIEW, ENTITY_KEYS, type EntityKey, GROUP_IDS } from "../seed/group-audit";

const E0 = seedScenario();
const at = (time: string) => `2026-09-14T${time}:00-05:00`;
export const AUD32_WORK_ITEM = GROUP_IDS.workItem;
export const AUD32_CONSOLIDATION = GROUP_IDS.consolidation;
export const STEPS = ["details", "structure", "trial_balances", "review"] as const;
export type Aud32Step = (typeof STEPS)[number];

const FILES: Record<EntityKey, string> = {
  holdings: "HP Holdings",
  operating: "HP Operating",
  manufacturing: "HP Manufacturing",
  distribution: "HP Distribution",
  real_estate: "HP Real Estate",
};
const CITY: Record<EntityKey, string> = {
  holdings: "Chicago, IL",
  operating: "Chicago, IL",
  manufacturing: "Dayton, OH",
  distribution: "Houston, TX",
  real_estate: "Dayton, OH",
};

type Variant = "a" | "b" | "c" | "d" | "e" | "f";

function prior(key: EntityKey, id: string, variant: Variant): TrialBalanceSlotOut {
  const missing = key === "real_estate" && (variant === "a" || variant === "f");
  const notNeeded = key === "real_estate" && (variant === "d" || variant === "e");
  return {
    id: `${id}-prior`,
    label: "prior",
    period_kind: "prior",
    period_start: "2025-01-01",
    period_end: "2025-12-31",
    state: missing ? "missing" : notNeeded ? "not_needed" : "attached",
    file_name: missing || notNeeded ? null : `${FILES[key]} TB 2025-12`,
    total_debits: null,
    not_needed_reason: notNeeded ? "Formed Jan 2026; no prior-year trial balance" : null,
  };
}

function entity(e: ConsolidationEntityOut, i: number, variant: Variant): ConsolidationEntityOut {
  const key = ENTITY_KEYS[i] as EntityKey;
  const interim = e.trial_balances[0] as TrialBalanceSlotOut;
  const slots =
    variant === "b" || variant === "c"
      ? []
      : [
          {
            ...interim,
            file_name: `${FILES[key]} TB 2026-08`,
            state:
              variant === "f" && key === "distribution"
                ? ("needs_reauth" as const)
                : interim.state,
          },
          prior(key, interim.id, variant),
        ];
  return { ...e, city: CITY[key], trial_balances: slots };
}

export function consolidation(variant: Variant): ConsolidationOut {
  const missing =
    variant === "a" || variant === "f" ? ["Harlow & Pike Real Estate, LLC · Prior"] : [];
  const finalized = variant === "e";
  return {
    ...CONSOLIDATION_REVIEW,
    status: finalized ? "finalized" : "draft",
    entities: CONSOLIDATION_REVIEW.entities.map((e, i) => entity(e, i, variant)),
    missing,
    finalized_by_name: finalized ? "Omar Haddad" : null,
    finalized_at: finalized ? at("10:48") : null,
    row_version: finalized ? 4 : 3,
    allowed_actions: finalized
      ? ["consolidation.lock"]
      : missing.length > 0
        ? ["consolidation.edit"]
        : ["consolidation.edit", "consolidation.finalize"],
  };
}

const C = "/v1/audits/{work_item_id}/consolidations/{consolidation_id}";

function frame(state: Variant, clock: string): Scenario {
  let variant: Variant = state;
  return {
    state,
    persona: "omar-haddad",
    clock: at(clock),
    handlers: {
      ...E0.handlers,
      [`GET ${C}`]: () => json(consolidation(variant)),
      [`POST ${C}/trial-balances/{tb_id}/not-needed`]: () => {
        variant = "d";
        const re = consolidation("d").entities[4] as ConsolidationEntityOut;
        return json(re.trial_balances[1]);
      },
      [`POST ${C}/finalize`]: () => {
        variant = "e";
        return json(consolidation("e"));
      },
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a", "10:44"),
  b: frame("b", "10:31"),
  c: frame("c", "10:36"),
  d: frame("d", "10:47"),
  e: frame("e", "10:48"),
  f: frame("f", "10:44"),
});

export type Aud32State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Aud32State[];
/** The wizard step each state opens on. */
export const STEP_OF: Record<Aud32State, Aud32Step> = {
  a: "trial_balances",
  b: "details",
  c: "structure",
  d: "review",
  e: "review",
  f: "trial_balances",
};
