// CLI-03 fixture scenarios (T-06-T23, DEC-5636; T-06-T40, TASK-8836; docs/screens/CLI-03.md): one per
// artboard, with the contract's persona and demo clock, serving `seed/cli03.ts` in the artboard's
// variant. Writes (add, edit, end, layout) answer as the services would; the gallery never persists.
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { type GraphVariant, graph } from "../seed/cli03";

function handlers(variant: GraphVariant): Record<string, FixtureHandler> {
  return {
    "GET /v1/clients/{client_id}/relationship-graph": () => json(graph(variant)),
    "POST /v1/clients/{client_id}/relationships": () =>
      json({ rel_id: "00000000-0000-4000-8000-0000000000aa" }, 201),
    "PATCH /v1/relationships/{rel_id}": () =>
      json({ rel_id: "00000000-0000-4000-8000-0000000000aa" }),
    "POST /v1/relationships/{rel_id}/end": () =>
      json({ rel_id: "00000000-0000-4000-8000-0000000000aa" }),
    "PUT /v1/users/me/graph-layouts/{client_id}": () => json({ saved: true }),
  };
}

function at(state: string, persona: string, clock: string, variant: GraphVariant): Scenario {
  return { state, persona, clock, handlers: handlers(variant) };
}

export const scenarios = defineScenarios({
  a: at("a", "olivia-brandt", "2026-09-14T09:24:00-05:00", "ridgeline"), // Default graph (Jonah Feld selected; amber banner) · `ridgeline-graph`
  b: at("b", "olivia-brandt", "2026-09-14T09:24:00-05:00", "ridgeline"), // List view · `ridgeline-graph`
  c: at("c", "olivia-brandt", "2026-09-14T09:24:00-05:00", "trust"), // Trust variant (Calloway Family Trust) · `calloway-graph`
  d: at("d", "olivia-brandt", "2026-09-14T09:24:00-05:00", "external"), // External node (Not a Brightwater Hale client) · `external-node`
  e: at("e", "olivia-brandt", "2026-09-14T09:24:00-05:00", "single"), // Single entity (No relationships yet.) · `single-entity`
  f: at("f", "olivia-brandt", "2026-09-15T10:30:00-05:00", "released"), // After Ridgeline approval (K-1s released Sep 15) · `ridgeline-graph-released`
});

export type Cli03State = keyof typeof scenarios;
