// TAX-10 fixture scenarios (T-08-T22; TASK-8936; DEC-5938; docs/screens/TAX-10.md): Samuel Ito
// on the Feld 2025 Form 1040 (a–e at their clocks; x1 the composed DF-04 state). The comparisons
// are the Python slice's (`seed/tax10.ts`); Accept and Edit write through the handlers.
import type { CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { capabilitiesFor } from "../seed/shell";
import { FELD_RETURN_ID } from "../seed/tax-compliance";
import { type Tax10State, applyWrite, twoYear } from "../seed/tax10";

export { FELD_RETURN_ID as TAX10_RETURN_ID };
const seed = getSeed();
const E0 = seedScenario();
const R = "/v1/tax-returns/{return_id}/two-year";

function at(state: Tax10State, clock: string): Scenario {
  return {
    state,
    persona: "samuel-ito",
    clock,
    get handlers(): Record<string, FixtureHandler> {
      let all = twoYear(state === "b" ? "a" : state);
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona }) => {
          const base: CapabilitiesOut = capabilitiesFor(seed, persona ?? "samuel-ito");
          return json({ ...base, flags: { ...base.flags, "tax.two_year": true } });
        },
        [`GET ${R}`]: ({ query }) =>
          json(
            query.get("filter") === "over_threshold"
              ? { ...all, filter: "over_threshold", lines: all.lines.filter((l) => l.flagged) }
              : all,
          ),
        [`POST ${R}/lines/{line_key}/explanation:accept`]: ({ params }) => {
          all = applyWrite(all, params.line_key ?? "", { accept: true });
          return json(all.lines.find((l) => l.line_key === params.line_key));
        },
        [`PUT ${R}/lines/{line_key}/explanation`]: ({ params, body }) => {
          all = applyWrite(all, params.line_key ?? "", { text: (body as { text: string }).text });
          return json(all.lines.find((l) => l.line_key === params.line_key));
        },
        [`POST ${R}:explain`]: () =>
          json({ run_id: "00000000-0000-4000-8000-0000000a10e1", started_at: clock }, 202),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "2026-09-14T10:05:00-05:00"), // Default · `feld-two-year-e0`
  b: at("b", "2026-09-14T10:05:00-05:00"), // Over threshold (the filter in the URL)
  c: at("c", "2026-09-14T10:07:00-05:00"), // All accepted · `feld-two-year-all-accepted`
  d: at("d", "2026-09-09T10:05:00-05:00"), // Unexplained · `feld-two-year-sep9`
  e: at("e", "2026-09-14T10:05:00-05:00"), // Agent explaining · `feld-two-year-explaining`
  x1: at("x1", "2026-09-14T10:05:00-05:00"), // Composed DF-04: agents off for this taxpayer
});
export type Tax10ScenarioState = keyof typeof scenarios;
