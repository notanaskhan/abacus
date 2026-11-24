// TXP-13 fixture scenarios (T-06-T23, DEC-5636; docs/screens/TXP-13.md): one per artboard, with the
// contract's persona and demo clock. The scenario seed each artboard names is in its comment;
// a–c serve the E0 seed until their screen tasks land. T-06-T45 (DEC-5937): d is Granite Peak's
// FY2026 Form 1120 with its hand-off landing from the Python slice (`seed/aud38.ts`).
import type { TaxReturnRecordOut } from "@abacus/api-client";
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seededReturnRecord } from "../handlers/tax-returns";
import { seedScenario } from "../scenario";
import { AUD38_LANDING, AUD38_TARGET } from "../seed/aud38";
import { TAX_RETURNS } from "../seed/tax";

export const TXP13_RETURN = AUD38_TARGET;
const E0 = seedScenario();

function at(state: string, persona: string, clock: string): Scenario {
  return { state, persona, clock, handlers: {} };
}

function record(): TaxReturnRecordOut {
  const base = seededReturnRecord(TAX_RETURNS[0]?.client ?? "") as TaxReturnRecordOut;
  return {
    ...base,
    row: {
      ...base.row,
      client_name: "Granite Peak Outdoor Supply, Inc.",
      form: "1120",
      tax_year: 2025,
    },
  };
}

function granite(state: string, landed: boolean): Scenario {
  return {
    state,
    persona: "leo-wong",
    clock: "2026-11-09T11:00:00-06:00",
    handlers: {
      ...E0.handlers,
      "GET /v1/tax-returns/{return_id}": () => json(record()),
      "GET /v1/tax-returns/{return_id}/handoff": () => json(landed ? AUD38_LANDING : {}),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "samuel-ito", "2026-09-14T09:24:00-05:00"), // 1120-S · AAA (Bluestem, Accepted, read-only) · `bluestem-1120s`
  b: at("b", "samuel-ito", "2026-09-14T09:24:00-05:00"), // 1120 · ASC 740 provision (Ashford 2,257,200) · `ashford-1120`
  b2: at("b2", "samuel-ito", "2026-09-14T09:24:00-05:00"), // Exception · unclassified difference (off 1,200) · `ashford-unclassified`
  c: at("c", "olivia-brandt", "2026-09-14T09:24:00-05:00"), // 990 · Part IX (Lakeshore 4,014,000) · `lakeshore-990`
  c2: at("c2", "olivia-brandt", "2026-09-14T09:24:00-05:00"), // 990 · Allocation basis · `lakeshore-990`
  c3: at("c3", "olivia-brandt", "2026-09-14T09:24:00-05:00"), // 990 · Building (skeleton) · `lakeshore-990-building`
  d: granite("d", true), // 1120 · from the audit (Granite Peak) · `granite-peak-1120`
});

export type Txp13State = keyof typeof scenarios;
/** T-06-T45: Granite Peak's 1120 with no hand-off (no artboard; the screen's empty case). */
export const noHandoff: Scenario = granite("none", false);
