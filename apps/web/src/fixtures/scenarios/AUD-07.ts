// AUD-07 Materiality (A-04-T10; A-04 §5.3; docs/screens/AUD-07.md): one fixture scenario per
// artboard, each the AUD-02 cockpit with Planning › Materiality open on Northwind PY2025, read
// through the A-04 stub's shapes and C3's card (seed/aud07.ts):
//
//   a            margaret-okonkwo  Mon Sep 14, 11:08 AM  v1 proposed 9:27; the card awaits the EP
//   b            hannah-leclerc    11:08 AM              radios disabled, the banner, Remind
//   c            margaret-okonkwo  11:12 AM              v2 decided; v1 superseded; rail Complete
//   d            margaret-okonkwo  Tue Oct 6, 11:20 AM   v3 reassessed at final, no change
//   e            margaret-okonkwo  11:08 AM              override: v3 revised with the impact list
//   off          margaret-okonkwo  11:08 AM              `assurance.materiality` off: C-20
//   not_allowed  cole-hart         11:08 AM              walled from Northwind: 404
//   loading      margaret-okonkwo  11:08 AM              the record never answers
//   error        margaret-okonkwo  11:08 AM              the record answers 500
//
// Deciding in a moves the scenario to c. Dev and test only.

import type {
  AuditCockpitOut,
  CapabilitiesOut,
  DecisionCardOut,
  MaterialityPreviewIn,
} from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
  never,
} from "../../app-core/fixture-mode";
import { auditHandlers } from "../handlers/audits";
import { trustHandlers } from "../handlers/trust";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  AUD07_CARD,
  type Aud07Variant,
  aud07Card,
  aud07Record,
  computeThresholds,
} from "../seed/aud07";
import { capabilitiesFor } from "../seed/shell";
import { DOCUMENTS } from "../seed/trust";

const seed = getSeed();
const E0 = seedScenario();
const AT_1108 = "2026-09-14T11:08:00-05:00";
const AT_1112 = "2026-09-14T11:12:00-05:00";
const AT_OCT6 = "2026-10-06T11:20:00-05:00";
const NOT_FOUND = { detail: "not_found" };
const M = "/v1/engagements/{engagement_id}/materiality";

export { AUD07_CARD };

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "margaret-okonkwo");
  return {
    ...base,
    capabilities: [...base.capabilities, "engagement.read_metadata"],
    flags: { ...base.flags, "audits.cockpit": true, "assurance.materiality": on },
  };
}

/** The cockpit with the Materiality row as the state draws it ("Complete · 11:12 AM" once decided). */
function cockpitWith(variant: Aud07Variant): Record<string, FixtureHandler> {
  const base = auditHandlers(seed, "run");
  const cockpit = base["GET /v1/audits/{work_item_id}/cockpit"];
  if (cockpit === undefined) return base;
  return {
    ...base,
    "GET /v1/audits/{work_item_id}/cockpit": async (request) => {
      const response = await cockpit(request);
      if (!response.ok || variant === "a" || variant === "b") return response;
      const body = (await response.json()) as AuditCockpitOut;
      const bands = (body.bands ?? []).map((band) => ({
        ...band,
        rows: (band.rows ?? []).map((row) =>
          row.key === "materiality"
            ? {
                ...row,
                section_state: "draft_ready" as const,
                sub_line: "Complete · 11:12 AM",
                blocked_on_name: null,
                blocked_on_user_id: null,
              }
            : row,
        ),
      }));
      return json({ ...body, bands });
    },
  };
}

/** The A-04 materiality reads and C3's card for one variant; a decide moves a to c. */
export function materialityHandlers(start: Aud07Variant): Record<string, FixtureHandler> {
  let variant = start;
  const card = (): DecisionCardOut => aud07Card(variant);
  return {
    [`GET ${M}/current`]: () => json(aud07Record(variant)),
    [`POST ${M}/preview`]: ({ body }) => {
      const out = computeThresholds(body as MaterialityPreviewIn);
      return out === null ? json({ detail: "outside_policy" }, 409) : json(out);
    },
    "GET /v1/decision-cards/{card_id}": ({ params }) =>
      params.card_id === AUD07_CARD ? json(card()) : json(NOT_FOUND, 404),
    "POST /v1/decision-cards/{card_id}/decide": ({ params }) => {
      if (params.card_id !== AUD07_CARD || variant !== "a") return json(NOT_FOUND, 404);
      variant = "c";
      return json(card());
    },
    "POST /v1/decision-cards/{card_id}/notify": () =>
      json({ notified_user_id: card().card.reserved_user_id, at: AT_1108 }),
    "POST /v1/decision-cards/{card_id}/analysis-requests": () => json(card()),
  };
}

function walled(): Record<string, FixtureHandler> {
  return {
    [`GET ${M}/current`]: () => json(NOT_FOUND, 404),
    [`POST ${M}/preview`]: () => json(NOT_FOUND, 404),
    "GET /v1/decision-cards/{card_id}": () => json(NOT_FOUND, 404),
  };
}

function frame(
  state: string,
  clock: string,
  options: {
    persona?: string;
    variant?: Aud07Variant;
    on?: boolean;
    materiality?: Record<string, FixtureHandler>;
  } = {},
): Scenario {
  const variant = options.variant ?? "a";
  const on = options.on ?? true;
  return {
    state,
    persona: options.persona ?? "margaret-okonkwo",
    clock,
    // A getter: every install starts the card at its variant again (a Decide moves a to c).
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        ...trustHandlers({ documents: DOCUMENTS, citations: [] }),
        ...cockpitWith(variant),
        "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona, on)),
        ...(options.materiality ?? materialityHandlers(variant)),
      };
    },
  };
}

const reads = materialityHandlers("a");

export const scenarios = defineScenarios({
  a: frame("a", AT_1108),
  b: frame("b", AT_1108, { persona: "hannah-leclerc", variant: "b" }),
  c: frame("c", AT_1112, { variant: "c" }),
  d: frame("d", AT_OCT6, { variant: "d" }),
  e: frame("e", AT_1108, { variant: "e" }),
  off: frame("off", AT_1108, { on: false }),
  not_allowed: frame("not_allowed", AT_1108, { persona: "cole-hart", materiality: walled() }),
  loading: frame("loading", AT_1108, {
    materiality: { ...reads, [`GET ${M}/current`]: () => never() },
  }),
  error: frame("error", AT_1108, {
    materiality: { ...reads, [`GET ${M}/current`]: () => json({ detail: "internal" }, 500) },
  }),
});

export type Aud07State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Aud07State[];
