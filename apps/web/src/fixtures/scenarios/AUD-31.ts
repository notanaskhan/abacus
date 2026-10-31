// AUD-31 Trial balance mapping (A-03-T12; docs/screens/AUD-31.md): one fixture scenario per state
// this row builds, Caleb Dunn on Granite Peak FY2026 (single entity), read through C9 v2's shapes
// (seed/aud31.ts):
//
//   f            11:40 AM  confirmed Sep 11: 128 of 128, TB balanced 1 of 1 (at parity)
//   a2 (a′)      11:40 AM  needs review without suggestions: Other assets unmapped
//   b2 (b′)      10:50 AM  the rules running, 78 of 128; the run read polls
//   c2 (c′)      11:40 AM  change made: Other assets mapped by Caleb ("Edited by CD")
//   d2 (d′)      11:58 AM  confirmed in this session: the green banner, "Prepared · CD"
//   e2 (e′)      11:40 AM  changed after sign-off: a newer TB version after the confirm
//   off          `ledger.tb_mapping` off: C-20
//   loading      the mapping set never answers
//   error        the mapping set answers 500
//   not_allowed  a 404 (walled or no read): nothing, no count
//
// A write moves the scenario on: a change answers c′, a confirm d′. Dev and test only.

import type {
  AccountMappingEditIn,
  CapabilitiesOut,
  ListPageMappingSetSummaryOut,
} from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
  never,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  type Aud31Variant,
  FS_LINES,
  aud31Run,
  aud31Set,
  aud31Summary,
  groupingCatalogue,
  groupingLines,
} from "../seed/aud31";
import { granitePeakMapping } from "../seed/sampling";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const AT_1140 = "2026-09-14T11:40:00-05:00";
const NOT_FOUND = { detail: "not_found" };

/** Granite Peak FY2026's engagement as the C9 v2 stub names it. */
export const GRANITE_MAPPING_ENGAGEMENT = granitePeakMapping().engagement_id;

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "caleb-dunn");
  return { ...base, flags: { ...base.flags, "ledger.tb_mapping": on } };
}

/** The C9 v2 mapping reads and writes for one variant; a write moves the variant on. */
export function mappingHandlers(start: Aud31Variant): Record<string, FixtureHandler> {
  let variant = start;
  return {
    "GET /v1/engagements/{engagement_id}/mapping-sets": () =>
      json({
        items: [aud31Summary(variant)],
        next_cursor: null,
        total: 1,
        total_capped: false,
        counts: {},
        facets: {},
      } satisfies ListPageMappingSetSummaryOut),
    "GET /v1/mapping-sets/{mapping_set_id}": () => json(aud31Set(variant)),
    "GET /v1/mapping-sets/{mapping_set_id}/run": () => json(aud31Run(variant)),
    "PUT /v1/mapping-sets/{mapping_set_id}/accounts/{account_code}": ({ params, body }) => {
      const sent = body as AccountMappingEditIn;
      variant = "c2";
      const found = aud31Set(variant).rows.find((r) => r.account_code === params.account_code);
      if (found === undefined) return json(NOT_FOUND, 404);
      const line = FS_LINES.find((l) => l.id === sent.fs_line_id);
      return json({
        ...found,
        fs_line_id: sent.fs_line_id,
        fs_line_label: line?.label ?? found.fs_line_label,
        grouping_label: line?.grouping_label ?? found.grouping_label,
      });
    },
    "POST /v1/mapping-sets/{mapping_set_id}/confirm": () => {
      variant = "d2";
      return json(aud31Summary(variant));
    },
    "GET /v1/grouping-sets/catalogue": () => json(groupingCatalogue()),
    "GET /v1/grouping-sets/{grouping_set_id}/versions/{version_no}/lines": () =>
      json(groupingLines()),
  };
}

function frame(
  state: string,
  options: {
    variant?: Aud31Variant;
    clock?: string;
    on?: boolean;
    handlers?: Record<string, FixtureHandler>;
  } = {},
): Scenario {
  return {
    state,
    persona: "caleb-dunn",
    clock: options.clock ?? AT_1140,
    handlers: {
      ...E0.handlers,
      ...mappingHandlers(options.variant ?? "f"),
      ...options.handlers,
      "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona, options.on ?? true)),
    },
  };
}

export const scenarios = defineScenarios({
  f: frame("f"),
  a2: frame("a2", { variant: "a2" }),
  b2: frame("b2", { variant: "b2", clock: "2026-09-14T10:50:00-05:00" }),
  c2: frame("c2", { variant: "c2" }),
  d2: frame("d2", { variant: "d2", clock: "2026-09-14T11:58:00-05:00" }),
  e2: frame("e2", { variant: "e2" }),
  off: frame("off", { on: false }),
  loading: frame("loading", {
    handlers: { "GET /v1/mapping-sets/{mapping_set_id}": () => never() },
  }),
  error: frame("error", {
    handlers: {
      "GET /v1/mapping-sets/{mapping_set_id}": () => json({ detail: "internal" }, 500),
    },
  }),
  not_allowed: frame("not_allowed", {
    handlers: {
      "GET /v1/engagements/{engagement_id}/mapping-sets": () => json(NOT_FOUND, 404),
    },
  }),
});

export type Aud31State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Aud31State[];
