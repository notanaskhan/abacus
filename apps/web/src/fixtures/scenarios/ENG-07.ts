// ENG-07 fixture scenarios (T-08-T15, TASK-8841; docs/screens/ENG-07.md): one per artboard, with
// the contract's persona and demo clock, over `seed/eng07.ts`.
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { type Eng07Variant, manifest, rows } from "../seed/eng07";

function handlers(variant: Eng07Variant): Record<string, FixtureHandler> {
  return {
    "GET /v1/seasons/{tax_year}/manifests/{manifest_id}": () => json(manifest(variant)),
    "GET /v1/season-cohorts/{cohort_id}/rows": () => {
      const r = rows(variant === "executing" ? 3 : 5);
      return json({ items: r, total: r.length, next_cursor: null });
    },
    "POST /v1/season-cohorts/{cohort_id}/approve": () => json({}, 201),
    "POST /v1/season-asks/{ask_id}/answer": () => json({}),
  };
}

function at(state: string, clock: string, variant: Eng07Variant): Scenario {
  return { state, persona: "samuel-ito", clock, handlers: handlers(variant) };
}

export const scenarios = defineScenarios({
  a: at("a", "2026-01-12T10:15:00-06:00", "draft"), // Draft cohort under review · `season-ty2025-jan12`
  b: at("b", "2026-01-12T10:21:00-06:00", "approved"), // Approved · `season-ty2025-cohort5-approved`
  c: at("c", "2026-01-12T10:15:00-06:00", "executing"), // Executing · cohort 3 · `season-ty2025-cohort3-executing`
  d: at("d", "2026-01-12T10:15:00-06:00", "draft"), // Exceptions · `season-ty2025-jan12`
  e: at("e", "2026-01-12T10:15:00-06:00", "draft"), // Agent asks · `season-ty2025-jan12`
  x1: at("x1", "2026-01-12T10:15:00-06:00", "agentsOff"), // DF-04 planner unavailable · `season-ty2025-agents-off`
  x2: { state: "x2", persona: "samuel-ito", clock: "2026-01-12T10:15:00-06:00", handlers: {} }, // C-20 flag off · `season-flag-off`
});

export type Eng07State = keyof typeof scenarios;
