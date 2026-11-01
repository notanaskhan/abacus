// The AUD-11 reads on fixtures (A-03-T11): the work item's sample sets (the picker), one sample
// set's version, its items with the server's search, and its population. Answers come from
// seed/sampling.ts in the server's shapes; nothing here draws or approves for anyone (INV-1). A-03-T15
// adds the fan-out's preview and create (AUD-11 c) and a draw in progress (e).

import type { ClientContactOut, SampleSetOut, SampleSetSummaryOut } from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { stableId } from "../seed/prng";
import { drawProgress, participantItems } from "../seed/sampling";

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

// --- A-03-T15 (AUD-11 c, e) ----------------------------------------------------------------------

interface TemplateIn {
  description: string;
  contact_id?: string | null;
  third_party_contact_id?: string | null;
}

/** AUD-11 c: the recipients, and the fan-out's preview and create in the server's shapes (one
 * request per template per item; a template to a third party counts on POR-14). */
export function generateHandlers(
  set: SampleSetOut,
  contacts: ClientContactOut[],
): Record<string, FixtureHandler> {
  const counts = (body: unknown): { total: number; por03: number; por14: number } => {
    const templates = ((body as { templates?: TemplateIn[] } | null)?.templates ?? []).length;
    const third = ((body as { templates?: TemplateIn[] } | null)?.templates ?? []).filter(
      (t) => t.third_party_contact_id != null,
    ).length;
    const n = set.items_total;
    return { total: templates * n, por03: (templates - third) * n, por14: third * n };
  };
  const name = (id: string | null | undefined): string =>
    contacts.find((c) => c.id === id)?.display_name ?? "";
  return {
    "GET /v1/engagements/{engagement_id}/client-contacts": ({ params }) =>
      json(params.engagement_id === set.engagement_id ? contacts : []),
    "POST /v1/sample-sets/{sample_set_id}/versions/{version_no}/item-requests/preview": ({
      body,
    }) => {
      const c = counts(body);
      const templates = (body as { templates?: TemplateIn[] }).templates ?? [];
      const by = new Map<string, { name: string; surface: string; requests: number }>();
      for (const t of templates) {
        const third = t.third_party_contact_id != null;
        const who = third ? t.third_party_contact_id : t.contact_id;
        const key = `${who ?? ""}:${third ? "14" : "03"}`;
        const row = by.get(key) ?? {
          name: name(who),
          surface: third ? "POR-14" : "POR-03",
          requests: 0,
        };
        row.requests += set.items_total;
        by.set(key, row);
      }
      return json({
        total: c.total,
        by_surface: { "POR-03": c.por03, "POR-14": c.por14 },
        recipients: [...by.values()].map((r) => ({
          ...r,
          organisation: r.surface === "POR-14" ? "Keystone" : null,
        })),
      });
    },
    "POST /v1/sample-sets/{sample_set_id}/versions/{version_no}/item-requests": ({ body }) => {
      const c = counts(body);
      return json(
        {
          created: c.total,
          by_surface: { "POR-03": c.por03, "POR-14": c.por14 },
          batch_id: stableId("batch:northwind-sample-v2"),
        },
        201,
      );
    },
  };
}

/** AUD-11 e: the version being drawn, polled through `…/draw`. */
export function drawingHandlers(set: SampleSetOut, done: number): Record<string, FixtureHandler> {
  return {
    "GET /v1/sample-sets/{sample_set_id}/versions/{version_no}/draw": () =>
      json(drawProgress(done)),
    "GET /v1/sample-sets/{sample_set_id}": ({ params }) =>
      params.sample_set_id === set.id ? json(set) : json({ detail: "not_found" }, 404),
  };
}
