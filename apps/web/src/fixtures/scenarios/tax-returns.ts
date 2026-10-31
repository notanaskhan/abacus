// T-02's six screens: one scenario per artboard with T-02 §5.3's persona and clock (T-02-T08).
// New portal personas: `nora-calloway` and `pell-street-member` ("Pell Street Ventures LLC ·
// authorized member"; no invented name). Each screen's build re-exports its own scenarios.
import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import { k1PackageHandlers } from "../handlers/k1-packages";
import { portalHandlers } from "../handlers/portal";
import { portalK1Handlers } from "../handlers/portal-k1s";
import { portalQuestionnaireHandlers } from "../handlers/portal-questionnaires";
import { taxReturnHandlers } from "../handlers/tax-returns";
import { seedScenario } from "../scenario";
import type { K1Variant } from "../seed/k1-packages";
import type { Por13Variant } from "../seed/portal-k1s";
import type { OverviewVariant } from "../seed/tax-return-overview";

const E0_CLOCK = "2026-09-14T09:24:00-05:00";
const E0 = seedScenario();

const at = (
  state: string,
  persona: string,
  clock = E0_CLOCK,
  variant?: OverviewVariant,
): Scenario => ({
  state,
  persona,
  clock,
  handlers: { ...E0.handlers, ...taxReturnHandlers(variant) },
});

export const tax01 = defineScenarios({
  a: at("a", "samuel-ito"),
  b: at("b", "samuel-ito"),
  c: at("c", "samuel-ito"),
  d: at("d", "samuel-ito"),
  e: at("e", "samuel-ito"),
  f: at("f", "samuel-ito"),
  // g: loading; the rows never answer (the tiles hold their place, T1e).
  g: {
    ...at("g", "samuel-ito"),
    handlers: {
      ...at("g", "samuel-ito").handlers,
      "GET /v1/tax-returns": () => new Promise<Response>(() => undefined),
    },
  },
});

// TAX-02 (T-02-T14): each artboard answers its return's record and overview (seed
// tax-return-overview.ts); f is a's return whose record and overview never answer.
export const tax02 = defineScenarios({
  a: at("a", "samuel-ito", E0_CLOCK, "a"),
  b: at("b", "samuel-ito", E0_CLOCK, "b"),
  c: at("c", "samuel-ito", "2026-02-03T09:24:00-06:00", "c"),
  d: at("d", "samuel-ito", E0_CLOCK, "d"),
  e: at("e", "samuel-ito", "2026-09-19T09:24:00-05:00", "e"),
  f: {
    ...at("f", "samuel-ito", E0_CLOCK, "a"),
    handlers: {
      ...at("f", "samuel-ito", E0_CLOCK, "a").handlers,
      "GET /v1/tax-returns/{return_id}": () => new Promise<Response>(() => undefined),
      "GET /v1/tax-returns/{return_id}/overview": () => new Promise<Response>(() => undefined),
    },
  },
});

export const tax03 = defineScenarios({
  a: at("a", "kevin-osei"),
  a2: at("a2", "kevin-osei"),
  b: at("b", "kevin-osei", "2026-09-14T09:26:00-05:00"),
  c: at("c", "kevin-osei", "2026-09-15T09:02:00-05:00"),
  d: at("d", "kevin-osei", "2026-09-15T10:30:00-05:00"),
  e: at("e", "kevin-osei"),
  f: at("f", "kevin-osei"),
});

// TXP-12 (T-02-T25): each artboard's K-1 rows and release check (seed/k1-packages.ts).
const at12 = (state: string, variant: K1Variant, clock = E0_CLOCK): Scenario => {
  const base = at(state, "samuel-ito", clock);
  return { ...base, handlers: { ...base.handlers, ...k1PackageHandlers(variant, base.handlers) } };
};

export const txp12 = defineScenarios({
  a: at12("a", "drafts"),
  a2: at12("a2", "drafts"),
  a3: at12("a3", "drafts"),
  a4: at12("a4", "drafts"),
  a5: at12("a5", "approved", "2026-09-15T10:28:00-05:00"),
  b: at12("b", "released", "2026-09-15T10:30:00-05:00"),
  b2: at12("b2", "released", "2026-09-15T10:30:00-05:00"),
  c: at12("c", "drafts"),
  d: at12("d", "drafts"),
  e: at12("e", "amended", "2026-10-05T09:24:00-05:00"),
  f: at12("f", "drafts"),
});

// T-02-T24: POR-05's questionnaires by artboard on top of the tax handlers.
const at05 = (state: string, persona: string): Scenario => {
  const base = at(state, persona);
  return {
    ...base,
    handlers: {
      ...base.handlers,
      ...portalHandlers({ clock: E0_CLOCK }),
      ...portalQuestionnaireHandlers(state),
    },
  };
};

export const por05 = defineScenarios({
  a: at05("a", "claire-feld"),
  b: at05("b", "claire-feld"),
  c: at05("c", "claire-feld"),
  d: at05("d", "dana-kowalski"),
  e: at05("e", "luis-ferrante"),
  f: at05("f", "claire-feld"),
});

// T-02-T27: POR-13's K-1s by artboard (seed/portal-k1s.ts) on the portal handlers.
const at13 = (state: string, persona: string, variant: Por13Variant, clock: string): Scenario => {
  const base = at(state, persona, clock);
  const portal = { ...base.handlers, ...portalHandlers({ clock }) };
  return { ...base, handlers: { ...portal, ...portalK1Handlers(variant, portal) } };
};

export const por13 = defineScenarios({
  a: at13("a", "nora-calloway", "nora_released", "2026-09-29T18:40:00-05:00"),
  b: at13("b", "pell-street-member", "pell_expected", E0_CLOCK),
  c: at13("c", "pell-street-member", "pell_released", "2026-09-15T09:24:00-05:00"),
  d: at13("d", "nora-calloway", "nora_released", "2026-09-29T18:40:00-05:00"),
  e: at13("e", "nora-calloway", "nora_amended", "2026-10-05T09:24:00-05:00"),
  f: at13("f", "meera-shah", "meera_expected", E0_CLOCK),
});
