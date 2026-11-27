// TXT-01 Review › Instrument: one fixture scenario per artboard and composed state (T-07-T15;
// T-07 §5.3; docs/screens/TXT-01.md). All at E0, Mon Sep 14, 2026, 9:24 AM CT: Samuel Ito (Tax
// Manager) on a–c, Kevin Osei (Tax Preparer) on d1–d3. Data: the Calloway instrument fixtures
// (seed/instrument.ts) over the return the board seeds (seed/tax.ts):
//
//   a   Proposed: 7 determinations, 6 clause chips, Trust type lit with III(a) and IV(a)
//   a2  a, with the interact `hoverChip('IV(a)')`: the reader scrolls to and lights Art. IV(a)
//   a3  a, with the interact `clickPassage('Art. II')`: the popover lists Fiduciary accounting income
//   a4  a, with `?ov=signoff` (SHL-12 L3, the route's overlay)
//   b   Approved: L3 by Samuel Ito Sep 14; locked; the button reads Approved (disabled)
//   c   Scenario · principal invaded: the amber banner and the note (composed by the server)
//   d   Unread: no highlights; "Instrument not read yet" + Read instrument
//   d1  Agents off (composed): Record… on every row; no Read instrument
//   d2  Reading (composed): "Checking citation 4 of 6"
//   d3  Consent required (composed): "§7216 AI consent — Calloway Family Trust (1 of 2 signed)"
//
// They live under fixtures/ (dev and test only); src/screens/TXT-01/scenarios.ts re-exports them.

import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { DEMO_INSTANT } from "../seed/clock";
import {
  INSTRUMENT_IDS,
  type InstrumentState,
  callowayClauses,
  callowayInstrument,
  callowayText,
} from "../seed/instrument";
import { capabilitiesFor } from "../seed/shell";
import { TAX_RETURNS } from "../seed/tax/tax-returns";

const E0 = seedScenario();

/** The Calloway Family Trust's 2025 Form 1041 on the board's seed. */
export const CALLOWAY_RETURN =
  TAX_RETURNS.find((r) => r.client === "Calloway Family Trust")?.id ?? "calloway";

function at(state: string, data: InstrumentState, persona: string): Scenario {
  const handlers: Record<string, FixtureHandler> = {
    "GET /v1/tax/returns/{return_id}/instrument": () =>
      json({ ...callowayInstrument(data), return_id: CALLOWAY_RETURN }),
    "GET /v1/tax/governing-instruments/{instrument_id}/clauses": ({ params }) =>
      params.instrument_id === INSTRUMENT_IDS.instrument
        ? json(callowayClauses())
        : json({ detail: "not_found" }, 404),
    "GET /v1/evidence-versions/{version_id}/text": ({ params }) =>
      params.version_id === INSTRUMENT_IDS.version
        ? json(callowayText())
        : json({ detail: "not_found" }, 404),
    "POST /v1/tax/returns/{return_id}/instrument/read": () =>
      json({ run_id: INSTRUMENT_IDS.run }, 202),
  };
  return {
    state,
    persona,
    clock: DEMO_INSTANT,
    get handlers() {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona: who }: { persona?: string | undefined }) => {
          const base = capabilitiesFor(getSeed(), who ?? persona);
          return json(base); // T-06-T69: the seed's `tax_returns` entitlement opens TXT-01/02
        },
        ...handlers,
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "proposed", "samuel-ito"),
  a2: at("a2", "proposed", "samuel-ito"),
  a3: at("a3", "proposed", "samuel-ito"),
  a4: at("a4", "proposed", "samuel-ito"),
  b: at("b", "approved", "samuel-ito"),
  c: at("c", "invaded", "samuel-ito"),
  d: at("d", "unread", "samuel-ito"),
  d1: at("d1", "agents_off", "kevin-osei"),
  d2: at("d2", "reading", "kevin-osei"),
  d3: at("d3", "consent", "kevin-osei"),
});

export type Txt01State = keyof typeof scenarios;
