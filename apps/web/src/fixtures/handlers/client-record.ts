// The CLI-02 client record routes over the seed (P-07-T19; docs/contracts/clients.md): the
// record, its overview, its relationships, the PATCH of the editable fields with `seen_version`,
// and the TIN reveal. Typed with the generated client. A walled or unknown client answers 404
// exactly like an absent one (INV-3, DEC-43); the reveal returns the plain value once with
// `remask_after_seconds` 10 and is the only payload that carries it. Writes change this handler
// set's own copy, so a scenario's reveal or partner change never leaks into another.

import type {
  ClientPatchIn,
  ClientRecordOut,
  ListPageClientRelationshipOut,
  TinRevealIn,
  TinRevealOut,
} from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import { DEFAULT_PERSONA } from "../handlers";
import type { Seed } from "../seed";
import { type ClientRecordFixture, clientRecords } from "../seed/client-records";

const NOT_FOUND = { detail: "not found" };

export interface ClientRecordHandlerOptions {
  /** Drop a record's overview sections that need content reads (a metadata-only firm admin). */
  metadataOnly?: boolean;
}

export function clientRecordHandlers(
  seed: Seed,
  options: ClientRecordHandlerOptions = {},
): Record<string, FixtureHandler> {
  const records = new Map<string, ClientRecordFixture>(
    Object.values(clientRecords(seed)).map((f) => [f.record.id, structuredClone(f)]),
  );
  const walled = (request: FixtureRequest): Set<string> => {
    const who = request.persona ?? DEFAULT_PERSONA;
    return new Set(seed.walls.filter((w) => w.personSlug === who).map((w) => w.clientId));
  };
  const find = (request: FixtureRequest): ClientRecordFixture | undefined => {
    const id = request.params.client_id ?? "";
    return walled(request).has(id) ? undefined : records.get(id);
  };
  const byEntity = (request: FixtureRequest): ClientRecordFixture | undefined => {
    const id = request.params.entity_id ?? "";
    const found = [...records.values()].find((f) => f.record.entities.some((e) => e.id === id));
    return found === undefined || walled(request).has(found.record.id) ? undefined : found;
  };
  return {
    "GET /v1/clients/{client_id}": (request) => {
      const found = find(request);
      return found === undefined ? json(NOT_FOUND, 404) : json(found.record);
    },
    "GET /v1/clients/{client_id}/overview": (request) => {
      const found = find(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      if (options.metadataOnly !== true) return json(found.overview);
      const metadata = new Set(["client.read", "engagement.read_metadata"]);
      return json({
        ...found.overview,
        sections: found.overview.sections.filter((s) => metadata.has(s.read_action)),
      });
    },
    "GET /v1/clients/{client_id}/relationships": (request) => {
      const found = find(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      const body: ListPageClientRelationshipOut = {
        items: found.relationships,
        next_cursor: null,
        total: found.relationships.length,
      };
      return json(body);
    },
    "PATCH /v1/clients/{client_id}": (request) => {
      const found = find(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      const patch = request.body as ClientPatchIn;
      if (!(found.record.allowed_actions ?? []).includes("client.update")) {
        return json({ detail: "forbidden" }, 403);
      }
      if (patch.seen_version !== found.record.version) {
        return json({ detail: "stale_version", facts: { client_id: found.record.id } }, 409);
      }
      const next: ClientRecordOut = {
        ...found.record,
        ...(patch.relationship_partner_id == null
          ? {}
          : { relationship_partner_id: patch.relationship_partner_id }),
        ...(patch.descriptor == null ? {} : { descriptor: patch.descriptor }),
        version: found.record.version + 1,
      };
      found.record = next;
      return json(next);
    },
    "POST /v1/client-entities/{entity_id}/tin/reveal": (request) => {
      const found = byEntity(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      if (!(found.record.allowed_actions ?? []).includes("tin.reveal")) {
        return json({ detail: "forbidden" }, 403);
      }
      const reason = (request.body as TinRevealIn | null)?.reason;
      if (reason === undefined) return json({ detail: "validation" }, 422);
      const entityId = request.params.entity_id ?? "";
      const entity = found.record.entities.find((e) => e.id === entityId);
      const value = found.reveal[entityId];
      if (entity?.tin == null || value === undefined) return json(NOT_FOUND, 404);
      const body: TinRevealOut = {
        entity_id: entityId,
        kind: entity.tin.kind,
        value,
        remask_after_seconds: 10,
      };
      return json(body);
    },
  };
}
