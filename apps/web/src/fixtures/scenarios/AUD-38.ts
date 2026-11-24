// AUD-38 fixture scenarios (T-06-T23 stubs; T-06-T45 handlers, DEC-5937; docs/screens/AUD-38.md):
// one per artboard with the contract's persona and clock, over Granite Peak's audit cockpit. The
// previews and the landing are the Python slice's (`seed/aud38.ts`); Hand off writes through the
// create handler, after which the 1120's landing answers (c).
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
import { AUD38_LANDING, type Aud38Preview, created, preview, targets } from "../seed/aud38";
import { capabilitiesFor } from "../seed/shell";
import { GRANITE_ENGAGEMENT, NORTHWIND_AUDIT } from "./AUD-06";

export { NORTHWIND_AUDIT as AUD38_AUDIT_ID };
const seed = getSeed();
const E0 = seedScenario();
const COCKPIT = "GET /v1/audits/{work_item_id}/cockpit";
const E = "/v1/engagements/{engagement_id}";

function at(state: string, clock: string, which: Aud38Preview, handedOff = false): Scenario {
  return {
    state,
    persona: "hannah-leclerc",
    clock,
    get handlers(): Record<string, FixtureHandler> {
      let landed = handedOff;
      const audits = auditHandlers(seed, "run");
      const cockpit = audits[COCKPIT];
      return {
        ...E0.handlers,
        ...audits,
        ...(cockpit === undefined
          ? {}
          : {
              [COCKPIT]: async (request) => {
                const response = await cockpit(request);
                if (!response.ok) return response;
                const body = (await response.json()) as AuditCockpitOut;
                return json({ ...body, engagement_id: GRANITE_ENGAGEMENT });
              },
            }),
        "GET /v1/me/capabilities": ({ persona }) => {
          const base: CapabilitiesOut = capabilitiesFor(seed, persona ?? "hannah-leclerc");
          return json({ ...base, flags: { ...base.flags, "tax.tb_handoff": true } });
        },
        [`GET ${E}/tax-handoff/targets`]: () => json(targets()),
        [`GET ${E}/tax-handoff/preview`]: () => json(preview(which)),
        [`POST ${E}/tax-handoffs`]: ({ body }) => {
          landed = true;
          return json(created((body as { tax_items?: string[] }).tax_items ?? []), 201);
        },
        "GET /v1/tax-returns/{return_id}/handoff": () =>
          json(landed || which === "superseded" ? AUD38_LANDING : {}),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "2026-11-09T10:29:00-06:00", "ready"), // Ready (both Send blank; 10:29)
  b: at("b", "2026-11-09T10:12:00-06:00", "needs_review"), // Needs review (first open)
  c: at("c", "2026-11-09T10:30:00-06:00", "ready"), // Handed off (toast), after Hand off
  d: at("d", "2026-10-21T09:00:00-05:00", "not_available"), // Not available (before G8)
  e: at("e", "2026-11-09T10:29:00-06:00", "superseded"), // Superseded
});

export type Aud38State = keyof typeof scenarios;
export { preview } from "../seed/aud38";
