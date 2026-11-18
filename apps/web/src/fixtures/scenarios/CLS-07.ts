// CLS-07 fixture scenarios (C-02-T15, DEC-5624; handoff CLS-07): Copperleaf August 2026 adjustments and thresholds; Raj Malhotra approves within threshold, Priya Raman approves held entries and posts.
// Each artboard's persona and clock (CDT until Sun Nov 1, 2026; CST after). C-02-T17 (DEC-5637):
// the close's entries come from the Python scenario's export (`seed/cls07.ts` over
// `scenario.cls07-entries.json`), on the E0 seed with the closes and posting flags on.
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { type Cls07Fixture, closeEntries, entries } from "../seed/cls07";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();

function at(state: Cls07Fixture, persona: string, clock: string): Scenario {
  return {
    state,
    persona,
    clock,
    get handlers() {
      return {
        ...E0.handlers,
        "GET /v1/work-items/{work_item_id}/proposed-entries:close": () =>
          json(closeEntries(state)),
        "GET /v1/work-items/{work_item_id}/proposed-entries": () =>
          json({ items: entries(state), next_cursor: null }),
        "GET /v1/me/capabilities": ({ persona: who }: { persona?: string | undefined }) => {
          const base = capabilitiesFor(getSeed(), who ?? persona);
          return json({
            ...base,
            flags: { ...base.flags, "closes.engine": true, "adjustments.posting": true },
          });
        },
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "raj-malhotra", "2026-09-14T09:24:00-05:00"),
  a2: at("a2", "raj-malhotra", "2026-09-14T09:24:00-05:00"),
  b: at("b", "raj-malhotra", "2026-09-14T09:31:00-05:00"),
  c: at("c", "priya-raman", "2026-09-14T10:12:00-05:00"),
  c2: at("c2", "priya-raman", "2026-09-14T10:21:00-05:00"),
  d: at("d", "priya-raman", "2026-09-14T10:22:00-05:00"),
  e: at("e", "raj-malhotra", "2026-09-14T09:24:00-05:00"),
  f: at("f", "raj-malhotra", "2026-09-14T09:24:00-05:00"),
  g: at("g", "raj-malhotra", "2026-09-14T09:24:00-05:00"),
});

export type Cls07State = keyof typeof scenarios;
export const INITIAL: Cls07State = "a";
