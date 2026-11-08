// EBP-03 Eligibility testing (A-05-T23; the handoff spec): one fixture scenario per artboard, each
// the AUD-02 cockpit with Testing › Eligibility Testing open on Northwind PY2025 (seed/ebp03.ts),
// Thu Sep 24, 10:15 AM CT, seen by Ana Cruz:
//
//   a  agent-tested, 2 exceptions (Kwame Mensah, Yuki Mori); row 22 marked no effect
//   b  the agent testing: rows 1-6 tested, the rest spinning (polled, 70 ms stagger)
//   c  row 22 "Needs human" until Ana marks the hire-date difference no effect
//   d  adopted: "✓ AC"
//   e  signed: "✓ AC" "✓ HL"
//   f  EBP-02's entry rule not verified yet: the rows, with no entry dates or missed amounts
//
// Dev and test only.

import type { AuditCockpitOut, CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { auditHandlers } from "../handlers/audits";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { type Ebp03Variant, ebp03Sample, ebp03Unverified } from "../seed/ebp03";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const AT = "2026-09-24T10:15:00-05:00";
const P = "/v1/audits/{work_item_id}/ebp";
const COCKPIT = "GET /v1/audits/{work_item_id}/cockpit";

function capabilities(persona: string | undefined): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "ana-cruz");
  return { ...base, flags: { ...base.flags, "audits.cockpit": true, "ebp.modules": true } };
}

/** The Northwind cockpit with Testing › Eligibility Testing ("In progress · 2 exceptions"). */
function withEligibility(base: FixtureHandler): FixtureHandler {
  return async (request) => {
    const response = await base(request);
    if (!response.ok) return response;
    const cockpit = (await response.json()) as AuditCockpitOut;
    const bands = (cockpit.bands ?? []).map((band, n, all) =>
      n !== all.length - 1
        ? band
        : {
            ...band,
            rows: [
              {
                key: "ebp_03",
                title: "Eligibility Testing",
                route: "EBP-03",
                link: "planned" as const,
                work_item_ref: cockpit.work_item_id,
                grammar: "sub_line" as const,
                section_state: "in_progress" as const,
                sub_line: "In progress · 2 exceptions",
                allowed_actions: [],
              },
              ...(band.rows ?? []),
            ],
          },
    );
    return json({ ...cockpit, bands });
  };
}

function frame(state: Ebp03Variant | "f"): Scenario {
  let sample = state === "f" ? ebp03Unverified() : ebp03Sample(state);
  return {
    state,
    persona: "ana-cruz",
    clock: AT,
    get handlers(): Record<string, FixtureHandler> {
      const audits = auditHandlers(seed, "run");
      const cockpit = audits[COCKPIT];
      return {
        ...E0.handlers,
        ...audits,
        ...(cockpit === undefined ? {} : { [COCKPIT]: withEligibility(cockpit) }),
        "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona)),
        [`GET ${P}/eligibility/sample`]: () => json(sample),
        "POST /v1/work-items/{work_item_id}/findings": () => json({ id: "fixture-finding" }, 201),
        "PUT /v1/audits/{work_item_id}/tests/{test_id}/items/{item_id}/results/{attribute}": ({
          params,
        }) => {
          sample = {
            ...sample,
            rows: sample.rows.map((r) =>
              r.item_id === params.item_id ? { ...r, result: "no_effect" as const } : r,
            ),
            needs_human: 0,
          };
          return json({ id: params.item_id }, 201);
        },
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b"),
  c: frame("c"),
  d: frame("d"),
  e: frame("e"),
  f: frame("f"),
});

export type Ebp03State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Ebp03State[];
