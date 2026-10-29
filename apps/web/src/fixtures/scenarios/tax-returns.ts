// T-02's six screens: one scenario per artboard with T-02 §5.3's persona and clock (T-02-T08).
// New portal personas: `nora-calloway` and `pell-street-member` ("Pell Street Ventures LLC ·
// authorized member"; no invented name). Each screen's build re-exports its own scenarios.
import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import { taxReturnHandlers } from "../handlers/tax-returns";
import { seedScenario } from "../scenario";

const E0_CLOCK = "2026-09-14T09:24:00-05:00";
const E0 = seedScenario();

const at = (state: string, persona: string, clock = E0_CLOCK): Scenario => ({
  state,
  persona,
  clock,
  handlers: { ...E0.handlers, ...taxReturnHandlers() },
});

export const tax01 = defineScenarios({
  a: at("a", "samuel-ito"),
  b: at("b", "samuel-ito"),
  c: at("c", "samuel-ito"),
  d: at("d", "samuel-ito"),
  e: at("e", "samuel-ito"),
  f: at("f", "samuel-ito"),
  g: at("g", "samuel-ito"),
});

export const tax02 = defineScenarios({
  a: at("a", "samuel-ito"),
  b: at("b", "samuel-ito"),
  c: at("c", "samuel-ito", "2026-02-03T09:24:00-06:00"),
  d: at("d", "samuel-ito"),
  e: at("e", "samuel-ito", "2026-09-19T09:24:00-05:00"),
  f: at("f", "samuel-ito"),
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

export const txp12 = defineScenarios({
  a: at("a", "samuel-ito"),
  a2: at("a2", "samuel-ito"),
  a3: at("a3", "samuel-ito"),
  a4: at("a4", "samuel-ito"),
  a5: at("a5", "samuel-ito", "2026-09-15T10:28:00-05:00"),
  b: at("b", "samuel-ito", "2026-09-15T10:30:00-05:00"),
  b2: at("b2", "samuel-ito", "2026-09-15T10:30:00-05:00"),
  c: at("c", "samuel-ito"),
  d: at("d", "samuel-ito"),
  e: at("e", "samuel-ito", "2026-10-05T09:24:00-05:00"),
  f: at("f", "samuel-ito"),
});

export const por05 = defineScenarios({
  a: at("a", "claire-feld"),
  b: at("b", "claire-feld"),
  c: at("c", "claire-feld"),
  d: at("d", "dana-kowalski"),
  e: at("e", "luis-ferrante"),
  f: at("f", "claire-feld"),
});

export const por13 = defineScenarios({
  a: at("a", "nora-calloway", "2026-09-29T18:40:00-05:00"),
  b: at("b", "pell-street-member"),
  c: at("c", "pell-street-member", "2026-09-15T09:24:00-05:00"),
  d: at("d", "nora-calloway", "2026-09-29T18:40:00-05:00"),
  e: at("e", "nora-calloway", "2026-10-05T09:24:00-05:00"),
  f: at("f", "meera-shah"),
});
