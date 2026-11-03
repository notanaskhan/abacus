// AUD-15 Findings register (A-06-T18; the handoff spec): the fixture scenarios, each on Northwind
// PY2025 (seed/aud15.ts):
//
//   a  hannah-leclerc     Mon Sep 28, 10:15 AM  F-01 proposed as a significant deficiency
//   b  margaret-okonkwo   10:15 AM              the partner concludes; Conclude severity…
//   c  margaret-okonkwo   4:12 PM               F-01 concluded by Margaret Okonkwo
//   d  hannah-leclerc     10:15 AM              F-01 and F-02 communicated Nov 20
//   e  hannah-leclerc     10:15 AM              F-07 selected: the projected misstatement
//   f  hannah-leclerc     10:15 AM              F-04 selected: exception for resolution
//   g  hannah-leclerc     10:15 AM              no findings yet
//
// Dev and test only.

import type { CapabilitiesOut, DecisionRaisedOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { auditHandlers } from "../handlers/audits";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  type Aud15Variant,
  DEC26,
  F01_CARD,
  aud15Card,
  aud15Detail,
  aud15List,
} from "../seed/aud15";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const AT = "2026-09-28T10:15:00-05:00";
const AT_C = "2026-09-28T16:12:00-05:00";
const NOT_FOUND = { detail: "not_found" };

function capabilities(persona: string | undefined): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "hannah-leclerc");
  return { ...base, flags: { ...base.flags, "audits.cockpit": true } };
}

function frame(
  variant: Aud15Variant,
  options: { persona?: string; clock?: string } = {},
): Scenario {
  const persona = options.persona ?? "hannah-leclerc";
  return {
    state: variant,
    persona,
    clock: options.clock ?? AT,
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        ...auditHandlers(seed, "run"),
        "GET /v1/me/capabilities": ({ persona: who }) => json(capabilities(who)),
        "GET /v1/work-items/{work_item_id}/findings": () => json(aud15List(variant)),
        "GET /v1/findings/{finding_id}": ({ params }) => {
          const detail = aud15Detail(variant, params.finding_id ?? "");
          return detail === null ? json(NOT_FOUND, 404) : json(detail);
        },
        "POST /v1/findings/{finding_id}/request-decision": () =>
          json({ decision_card_id: F01_CARD } satisfies DecisionRaisedOut, 201),
        "POST /v1/findings/{finding_id}/resolve": ({ params }) => {
          const detail = aud15Detail(variant, params.finding_id ?? "");
          return detail === null ? json(NOT_FOUND, 404) : json(detail);
        },
        "POST /v1/findings/{finding_id}/not-applicable": ({ params }) => {
          const detail = aud15Detail(variant, params.finding_id ?? "");
          return detail === null ? json(NOT_FOUND, 404) : json(detail);
        },
        "GET /v1/decision-cards/{card_id}": ({ params, persona: who }) =>
          params.card_id === F01_CARD
            ? json(aud15Card(variant, who ?? persona))
            : json(NOT_FOUND, 404),
        "GET /v1/audits/{work_item_id}/ebp/late-remittances": () => json([DEC26]),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b", { persona: "margaret-okonkwo" }),
  c: frame("c", { persona: "margaret-okonkwo", clock: AT_C }),
  d: frame("d"),
  e: frame("e"),
  f: frame("f"),
  g: frame("g"),
});

export type Aud15State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Aud15State[];

/** The finding each state opens selected (the queue's first row otherwise). */
export const SELECTED: Readonly<Partial<Record<Aud15State, string>>> = { e: "F-07", f: "F-04" };
