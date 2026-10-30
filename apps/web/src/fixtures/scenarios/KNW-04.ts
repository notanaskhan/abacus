// KNW-04 Firm standards & thresholds: one fixture scenario per read artboard a–h (K-02-T13; KNW-04
// handoff, Mon Sep 14, 2026, 9:24 AM CT; f after 11:12 AM). Data: seed/standards.ts through
// handlers/standards.ts. Priya Raman views every artboard; `draft_hidden` is Cole Hart (staff) on
// b, without the 1040 v7 draft; `flag_off` is the firm without `knowledge.firm_standards`;
// `no_examples` is the live product before C-01 registers its provider. i (K-02-T14) is Priya's
// draft v3 of AJE thresholds: payroll accruals $15,000 → $17,500 and other accrued expenses
// $10,000 → $12,500, effective Oct 1, 2026; `i_stale` answers 409 to a save (another partner saved
// first). j (deadline rules, Grace Holloway, the platform reference sets behind
// `rules.reference_sets`) is K-02-T17's.
//
// They live under fixtures/ (dev and test only); src/screens/KNW-04/scenarios.ts re-exports them.

import type { CapabilitiesOut } from "@abacus/api-client";
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { referenceSetsHandlers } from "../handlers/reference-sets";
import { standardsHandlers, type StandardsOptions } from "../handlers/standards";
import { STANDARDS } from "../seed/standards";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { DEMO_INSTANT } from "../seed/clock";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();
// f is rendered after Northwind's 11:12 AM decision.
const AFTER_DECISION = "2026-09-14T11:12:00-05:00";

function capabilities(persona: string, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona);
  return {
    ...base,
    capabilities: [...base.capabilities, "firm_standard.read", "reference_set.read"],
    flags: { ...base.flags, "knowledge.firm_standards": on, "rules.reference_sets": on },
  };
}

function at(
  state: string,
  persona = "priya-raman",
  options: StandardsOptions & { flag?: boolean; clock?: string } = {},
): Scenario {
  const on = options.flag ?? true;
  return {
    state,
    persona,
    clock: options.clock ?? DEMO_INSTANT,
    handlers: {
      ...E0.handlers,
      ...standardsHandlers(options),
      ...referenceSetsHandlers(),
      "GET /v1/me/capabilities": ({ persona: who }) => json(capabilities(who ?? persona, on)),
    },
  };
}

const AJE = STANDARDS.find((s) => s.key === "bh-aje-thresholds");
const V3 =
  AJE?.payload.kind === "aje_thresholds"
    ? {
        ...AJE.payload,
        rows: AJE.payload.rows.map((r) =>
          r.account_class === "Payroll accruals"
            ? { ...r, limit_usd: 17500 }
            : r.account_class === "Other accrued expenses"
              ? { ...r, limit_usd: 12500 }
              : r,
        ),
      }
    : undefined;
const DRAFT_V3: StandardsOptions["draft"] =
  V3 === undefined
    ? undefined
    : { key: "bh-aje-thresholds", version: 3, payload: V3, effective: "2026-10-01" };

export const scenarios = defineScenarios({
  a: at("a"),
  b: at("b"),
  c: at("c"),
  d: at("d"),
  e: at("e"),
  f: at("f", "priya-raman", { clock: AFTER_DECISION }),
  g: at("g"),
  h: at("h"),
  j: at("j", "grace-holloway"),
  draft_hidden: at("draft_hidden", "cole-hart"),
  no_examples: at("no_examples", "priya-raman", { noExamples: true }),
  flag_off: at("flag_off", "priya-raman", { flag: false }),
  i: at("i", "priya-raman", { draft: DRAFT_V3 }),
  i_stale: at("i_stale", "priya-raman", { draft: DRAFT_V3, staleOnSave: true }),
});

export type Knw04State = keyof typeof scenarios;
