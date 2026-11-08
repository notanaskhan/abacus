// EBP-02 Plan provisions review (A-05-T17; A-05 §3 F2; the handoff spec): one fixture scenario
// per artboard, each the AUD-02 cockpit with Fieldwork › Plan Review open on Northwind PY2025
// (seed/ebp02.ts), seen by Hannah Leclerc:
//
//   a            Thu Sep 24, 10:15 AM  20 of 20 verified, "✓ HL"
//   b            Mon Sep 14, 9:24 AM   agent draft: 0 of 20, "Agent draft"
//   b2           9:24 AM               `?version=1`: 18 rows, read-only
//   c            9:24 AM               SPD conflict: Entry dates "SPD: quarterly"
//   d            9:24 AM               amendment flag: Catch-up "Amended Jan 1, 2025"
//   e            9:24 AM               signed off: "Reviewed · HL Sep 17"
//   off          10:15 AM              `ebp.modules` off: C-20
//   not_allowed  cole-hart             walled from Northwind: 404
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
import { type Ebp02Variant, ebp02Review } from "../seed/ebp02";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const AT_A = "2026-09-24T10:15:00-05:00";
const AT = "2026-09-14T09:24:00-05:00";
const NOT_FOUND = { detail: "not_found" };
const P = "/v1/audits/{work_item_id}/ebp";
const COCKPIT = "GET /v1/audits/{work_item_id}/cockpit";

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "hannah-leclerc");
  return {
    ...base,
    flags: { ...base.flags, "audits.cockpit": true, "ebp.modules": on },
  };
}

/** The Northwind cockpit with the Fieldwork band's Plan Review row (the handoff's rail). */
function withPlanReview(base: FixtureHandler): FixtureHandler {
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
                key: "ebp_02",
                title: "Plan Review",
                route: "EBP-02",
                link: "planned" as const,
                work_item_ref: cockpit.work_item_id,
                grammar: "sub_line" as const,
                section_state: "draft_ready" as const,
                sub_line: "Reviewed · HL",
                allowed_actions: [],
              },
              ...(band.rows ?? []),
            ],
          },
    );
    return json({ ...cockpit, bands });
  };
}

function frame(
  state: string,
  options: {
    persona?: string;
    variant?: Ebp02Variant;
    on?: boolean;
    clock?: string;
    walled?: boolean;
  } = {},
): Scenario {
  const on = options.on ?? true;
  return {
    state,
    persona: options.persona ?? "hannah-leclerc",
    clock: options.clock ?? AT,
    get handlers(): Record<string, FixtureHandler> {
      const audits = auditHandlers(seed, "run");
      const cockpit = audits[COCKPIT];
      return {
        ...E0.handlers,
        ...audits,
        ...(cockpit === undefined ? {} : { [COCKPIT]: withPlanReview(cockpit) }),
        "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona, on)),
        [`GET ${P}/plan-reviews/current`]: ({ query }) =>
          options.walled === true
            ? json(NOT_FOUND, 404)
            : json(ebp02Review(query.get("version") === "1" ? "b2" : (options.variant ?? "a"))),
        "POST /v1/fields/{target_type}/{target_id}/{field_key}/ticks": () =>
          json({ id: "00000000-0000-4000-8000-000000000999" }, 201),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a", { clock: AT_A }),
  b: frame("b", { variant: "b" }),
  b2: frame("b2"),
  c: frame("c", { variant: "c" }),
  d: frame("d", { variant: "d" }),
  e: frame("e", { variant: "e" }),
  off: frame("off", { on: false, clock: AT_A }),
  not_allowed: frame("not_allowed", { persona: "cole-hart", walled: true }),
});

export type Ebp02State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Ebp02State[];
