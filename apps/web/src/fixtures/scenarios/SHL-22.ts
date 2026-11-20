// SHL-22 fixture scenarios (K-03-T08; TV-1): Harlow & Pike FS v5 → FS v6; Granite Peak held.
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { GRANITE, link, update } from "../seed/templates-v2";

const E = "/v1/engagements/{engagement_id}";
function at(
  state: string,
  persona: string,
  clock: string,
  l: Parameters<typeof link>[0],
  u: Parameters<typeof update>[0],
  applied = 0,
  engagement?: string,
): Scenario {
  return {
    state,
    persona,
    clock,
    handlers: {
      [`GET ${E}/template-link`]: () => json(link(l, engagement)),
      [`GET ${E}/template-update`]: () => json(update("dry_run")),
      [`GET ${E}/template-update/{update_id}`]: () => json(update(u, applied)),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "omar-haddad", "2026-10-01T10:18:00-05:00", "update_available", "dry_run"), // Default
  b: at("b", "omar-haddad", "2026-10-01T10:20:00-05:00", "update_available", "applying", 5), // Applying · 5 of 8
  c: at("c", "omar-haddad", "2026-10-01T10:21:00-05:00", "updated", "applied", 8), // Updated
  d: at("d", "hannah-leclerc", "2026-10-01T16:30:00-05:00", "held", "dry_run", 0, GRANITE), // Held
  e: at("e", "aiden-ward", "2026-10-01T10:18:00-05:00", "update_available", "dry_run"), // No permission
});
