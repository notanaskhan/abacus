// KNW-07 fixture scenarios (K-03-T08; TV-1): versions and rollout of BH Audit Methodology · FS.
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { CHANGES, USED_BY, rollout, version } from "../seed/templates-v2";

const V = "/v1/template-versions/{version_id}";
function at(
  state: string,
  clock: string,
  v6: "draft" | "published",
  run: "not_started" | "in_progress" = "not_started",
): Scenario {
  return {
    state,
    persona: "margaret-okonkwo",
    clock,
    handlers: {
      "GET /v1/template-versions": () =>
        json({
          items: [
            version("v6", v6),
            version("v5", v6 === "published" ? "deprecated" : "published"),
          ],
          next_cursor: null,
        }),
      [`GET ${V}`]: () => json(version("v6", v6)),
      [`GET ${V}/changes`]: () => json(CHANGES),
      [`GET ${V}/rollout`]: () => json(rollout(run)),
      [`GET ${V}/used-by`]: () => json(USED_BY),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "2026-10-01T09:45:00-05:00", "published"), // Published · actions set
  b: at("b", "2026-10-01T09:36:00-05:00", "draft"), // Draft · publish
  c: at("c", "2026-10-01T09:45:00-05:00", "published"), // Start rollout
  d: at("d", "2026-10-01T10:25:00-05:00", "published", "in_progress"), // Rollout in progress
  e: at("e", "2026-10-01T09:45:00-05:00", "published"), // Dry run
  f: at("f", "2026-10-01T09:45:00-05:00", "published"), // Deprecate FS v5
  g: at("g", "2026-10-01T09:45:00-05:00", "published"), // Used by
});
