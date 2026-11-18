// AUD-38 fixture scenarios (T-06-T23, DEC-5636; docs/screens/AUD-38.md): one per artboard, with the
// contract's persona and demo clock. The scenario seed each artboard names is in its comment;
// every state serves the E0 seed until the screen task's data handlers land (make fixtures).
import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";

function at(state: string, persona: string, clock: string): Scenario {
  return { state, persona, clock, handlers: {} };
}

export const scenarios = defineScenarios({
  a: at("a", "hannah-leclerc", "2026-11-09T10:29:00-06:00"), // Ready (both Send blank; 10:29) · `granite-peak-handoff`
  b: at("b", "hannah-leclerc", "2026-11-09T10:12:00-06:00"), // Needs review (first open) · `granite-peak-handoff`
  c: at("c", "hannah-leclerc", "2026-11-09T10:30:00-06:00"), // Handed off (toast) · `granite-peak-handoff`
  d: at("d", "hannah-leclerc", "2026-10-21T09:00:00-05:00"), // Not available (before G8) · `granite-peak-pre-release`
  e: at("e", "hannah-leclerc", "2026-11-09T10:29:00-06:00"), // Superseded · `granite-peak-superseded`
});

export type Aud38State = keyof typeof scenarios;
