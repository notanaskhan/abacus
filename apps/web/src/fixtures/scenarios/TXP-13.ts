// TXP-13 fixture scenarios (T-06-T23, DEC-5636; docs/screens/TXP-13.md): one per artboard, with the
// contract's persona and demo clock. The scenario seed each artboard names is in its comment;
// every state serves the E0 seed until the screen task's data handlers land (make fixtures).
import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";

function at(state: string, persona: string, clock: string): Scenario {
  return { state, persona, clock, handlers: {} };
}

export const scenarios = defineScenarios({
  a: at("a", "samuel-ito", "2026-09-14T09:24:00-05:00"), // 1120-S · AAA (Bluestem, Accepted, read-only) · `bluestem-1120s`
  b: at("b", "samuel-ito", "2026-09-14T09:24:00-05:00"), // 1120 · ASC 740 provision (Ashford 2,257,200) · `ashford-1120`
  b2: at("b2", "samuel-ito", "2026-09-14T09:24:00-05:00"), // Exception · unclassified difference (off 1,200) · `ashford-unclassified`
  c: at("c", "olivia-brandt", "2026-09-14T09:24:00-05:00"), // 990 · Part IX (Lakeshore 4,014,000) · `lakeshore-990`
  c2: at("c2", "olivia-brandt", "2026-09-14T09:24:00-05:00"), // 990 · Allocation basis · `lakeshore-990`
  c3: at("c3", "olivia-brandt", "2026-09-14T09:24:00-05:00"), // 990 · Building (skeleton) · `lakeshore-990-building`
  d: at("d", "leo-wong", "2026-11-09T11:00:00-06:00"), // 1120 · from the audit (Granite Peak) · `granite-peak-1120`
});

export type Txp13State = keyof typeof scenarios;
