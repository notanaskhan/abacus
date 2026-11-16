// AUD-33 Consolidated trial balance (A-09-T15; SPEC-658 AC-4.1, AC-4.2; handoff AUD-33 spec.md):
// one fixture scenario per state, Omar Haddad on Harlow & Pike interim 8/31/2026, read through
// C9 v2.1 and C8 v1.1 (seed/group-audit.ts):
//
//   a  2:05 PM  Level 1, all six eliminations posted (default)
//   b  1:33 PM  proposed by the agent: six Proposed cards, tallies Pending
//   c  1:45 PM  unbalanced: E3 off 10,000, Approve disabled, BALANCED off 10,000
//   d  2:05 PM  Level 2 · Operating Co.
//   e  2:05 PM  Adjustments: empty
//   f  2:20 PM  Locked
//   g  2:05 PM  entity tab Manufacturing
//
// Dev and test only.

import type { ConsolidatedTbOut, EliminationsOut } from "@abacus/api-client";
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import {
  CONSOLIDATED_TB_L1,
  CONSOLIDATED_TB_L2,
  ELIMINATIONS,
  GROUP_IDS,
} from "../seed/group-audit";

const E0 = seedScenario();
const at = (time: string) => `2026-09-14T${time}:00-05:00`;
export const AUD33_WORK_ITEM = GROUP_IDS.workItem;
export const AUD33_CONSOLIDATION = GROUP_IDS.consolidation;

type Variant = "a" | "b" | "c" | "d" | "e" | "f" | "g";

function eliminations(variant: Variant): EliminationsOut {
  if (variant !== "b" && variant !== "c") return ELIMINATIONS;
  return {
    ...ELIMINATIONS,
    items: ELIMINATIONS.items.map((e) => {
      const proposed = {
        ...e,
        status: "proposed" as const,
        approved_by_name: null,
        posted_at: null,
      };
      if (variant === "c" && e.display_code === "E3") {
        return {
          ...proposed,
          total_credit: "250000.00",
          off_by: "-10000.00",
          lines: e.lines.map((l) => (Number(l.credit) > 0 ? { ...l, credit: "250000.00" } : l)),
        };
      }
      return proposed;
    }),
  };
}

function tb(variant: Variant): ConsolidatedTbOut {
  const base = variant === "d" ? CONSOLIDATED_TB_L2 : CONSOLIDATED_TB_L1;
  if (variant === "b") {
    return {
      ...base,
      tallies: {
        ...base.tallies,
        balanced: "pending",
        intercompany: "pending",
        eliminations_posted: 0,
      },
    };
  }
  if (variant === "c") {
    return {
      ...base,
      tallies: {
        ...base.tallies,
        balanced: "off",
        off_by: "10000.00",
        intercompany: "off",
        intercompany_off_by: "2400000.00",
        total_assets: "53160000.00",
        eliminations_posted: 0,
      },
    };
  }
  return base;
}

const C = "/v1/audits/{work_item_id}/consolidations/{consolidation_id}";

function frame(state: Variant, clock: string): Scenario {
  return {
    state,
    persona: "omar-haddad",
    clock: at(clock),
    handlers: {
      ...E0.handlers,
      [`GET ${C}/tb`]: () => json(tb(state)),
      "GET /v1/consolidations/{consolidation_id}/eliminations": () => json(eliminations(state)),
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a", "14:05"),
  b: frame("b", "13:33"),
  c: frame("c", "13:45"),
  d: frame("d", "14:05"),
  e: frame("e", "14:05"),
  f: frame("f", "14:20"),
  g: frame("g", "14:05"),
});

export type Aud33State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Aud33State[];
