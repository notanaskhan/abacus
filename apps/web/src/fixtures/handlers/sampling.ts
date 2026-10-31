// The AUD-11 reads on fixtures (A-03-T11): the work item's sample sets (the picker), one sample
// set's version, its items with the server's search, and its population. Answers come from
// seed/sampling.ts in the server's shapes; nothing here draws, approves or generates (INV-1).

import type { SampleSetOut, SampleSetSummaryOut } from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { participantItems } from "../seed/sampling";

export interface SamplingFixture {
  sets: SampleSetSummaryOut[];
  set: SampleSetOut;
}

export function samplingHandlers(f: SamplingFixture): Record<string, FixtureHandler> {
  return {
    "GET /v1/work-items/{work_item_id}/sample-sets": () =>
      json({ items: f.sets, total: f.sets.length }),
    "GET /v1/sample-sets/{sample_set_id}": ({ params }) =>
      params.sample_set_id === f.set.id ? json(f.set) : json({ detail: "not_found" }, 404),
    "GET /v1/sample-sets/{sample_set_id}/versions/{version_no}/items": ({ query }) => {
      const q = (query.get("q") ?? "").trim().toLowerCase();
      const items = participantItems().filter(
        (i) =>
          q === "" ||
          (i.name ?? "").toLowerCase().includes(q) ||
          i.record_key.toLowerCase().includes(q),
      );
      return json({ items, total: items.length });
    },
    "GET /v1/populations/{population_id}": () => json(f.set.population),
  };
}

/** Every sampling read refused (a walled person, INV-3: 404 and no count). */
export function walledSampling(): Record<string, FixtureHandler> {
  const none: FixtureHandler = () => json({ detail: "not_found" }, 404);
  return {
    "GET /v1/work-items/{work_item_id}/sample-sets": none,
    "GET /v1/sample-sets/{sample_set_id}": none,
    "GET /v1/sample-sets/{sample_set_id}/versions/{version_no}/items": none,
    "GET /v1/populations/{population_id}": none,
  };
}
