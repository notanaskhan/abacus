// AUD-09 Internal control & exceptions (A-04-T32; the handoff spec): the fixture scenarios, each on
// Northwind PY2025 (seed/aud09.ts):
//
//   a            hannah-leclerc     Mon Sep 14, 12:24 PM  seven exceptions on Exceptions!B2:E8
//   b            hannah-leclerc     12:24 PM              `?cell=D2`: two citations in the footer
//   c            hannah-leclerc     12:24 PM              the O1 severity picker open on D2
//   d            hannah-leclerc     9:58 AM               the seeded failure: BH-EBP-140 step 8
//   e            hannah-leclerc     12:24 PM              `?sheet=internal-control`: five processes
//   f            margaret-okonkwo   Thu Sep 24            D2 concluded and communicated (fixture)
//   off          hannah-leclerc     12:24 PM              `assurance.internal_control` off: C-20
//   not_allowed  cole-hart          12:24 PM              walled from Northwind: 404
//
// Dev and test only.

import type { CapabilitiesOut } from "@abacus/api-client";
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
  AUD09_CITATIONS,
  AUD09_KEYSTONE,
  type Aud09Variant,
  aud09Exceptions,
  aud09Processes,
} from "../seed/aud09";
import { KNW03_RUN } from "../seed/knw03";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const AT = "2026-09-14T12:24:00-05:00";
const AT_D = "2026-09-14T09:58:00-05:00";
const AT_F = "2026-09-24T10:00:00-05:00";
const P = "/v1/engagements/{engagement_id}/internal-control";
const NOT_FOUND = { code: "not_found", message: "Not found." };

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "hannah-leclerc");
  return {
    ...base,
    flags: { ...base.flags, "audits.cockpit": true, "assurance.internal_control": on },
  };
}

function frame(
  state: string,
  options: {
    persona?: string;
    variant?: Aud09Variant;
    on?: boolean;
    clock?: string;
    failed?: boolean;
  } = {},
): Scenario {
  const on = options.on ?? true;
  const failed = options.failed ?? false;
  const variant = options.variant ?? "a";
  return {
    state,
    persona: options.persona ?? "hannah-leclerc",
    clock: options.clock ?? AT,
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        ...auditHandlers(
          seed,
          failed ? "failed" : "run",
          failed ? { agentRuns: [KNW03_RUN] } : {},
        ),
        "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona, on)),
        [`GET ${P}/exceptions`]: () => json(aud09Exceptions(variant)),
        [`GET ${P}/processes`]: () => json(aud09Processes()),
        "GET /v1/engagements/{engagement_id}/service-organizations": () =>
          json({
            items: [
              {
                id: AUD09_KEYSTONE,
                name: "Keystone",
                services: "Recordkeeping",
                relevant: true,
                evidence_type: "soc1_type2",
                status: "gap_found",
                soc_report_id: null,
                subservice_orgs: [],
                row_version: 1,
                allowed_actions: [],
              },
            ],
            total: 1,
          }),
        [`PATCH ${P}/exceptions/{sheet_row}/proposed-severity`]: ({ params, body }) => {
          const row = aud09Exceptions(variant).items.find(
            (r) => String(r.sheet_row) === params.sheet_row,
          );
          if (row === undefined) return json(NOT_FOUND, 404);
          const chosen = (body as { proposed_severity: typeof row.proposed_severity })
            .proposed_severity;
          return json({ ...row, proposed_severity: chosen, disposition: "proposed" });
        },
        "GET /v1/citations/{citation_id}": ({ params }) => {
          const found = AUD09_CITATIONS.find((c) => c.id === params.citation_id);
          return found === undefined ? json(NOT_FOUND, 404) : json(found);
        },
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b"),
  c: frame("c"),
  d: frame("d", { clock: AT_D, failed: true }),
  e: frame("e"),
  f: frame("f", { persona: "margaret-okonkwo", variant: "f", clock: AT_F }),
  off: frame("off", { on: false }),
  not_allowed: frame("not_allowed", { persona: "cole-hart" }),
});

export type Aud09State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Aud09State[];
