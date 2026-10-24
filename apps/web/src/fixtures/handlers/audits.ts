// The audits family routes over the seed in fixture mode (A-01-T06; docs/contracts/audits-cockpit.md):
// the AUD-01 index, Northwind's AUD-02 cockpit and the Source Documents aggregate. Typed with the
// generated client. A walled client's audits are absent from the index and answer 404 elsewhere
// (INV-3, DEC-43: no hidden count); a work item without a cockpit fixture answers 404. The rail
// grammar (run, idle, pills) is the scenario's choice; the seed's clock is the day.

import type { AuditEngagementStatus, AuditIndexRowOut } from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import { DEFAULT_PERSONA } from "../handlers";
import type { Seed } from "../seed";
import { type CockpitGrammar, northwindCockpit } from "../seed/audit-cockpit";
import { auditIndexPage, auditIndexRows, sourceDocuments } from "../seed/audits-index";
import { stableId } from "../seed/prng";

const NOT_FOUND = { detail: "not_found" };
type Segment = AuditIndexRowOut["segment"];
type Due = "any" | "7d" | "14d" | "30d";

export function auditHandlers(
  seed: Seed,
  grammar: CockpitGrammar = "run",
): Record<string, FixtureHandler> {
  const today = new Date(seed.clock.ms).toISOString().slice(0, 10);
  const rows = auditIndexRows(seed.engagements, seed.workItems, today);
  const visible = (request: FixtureRequest): AuditIndexRowOut[] => {
    const who = request.persona ?? DEFAULT_PERSONA;
    const walled = new Set(seed.walls.filter((w) => w.personSlug === who).map((w) => w.clientId));
    return rows.filter((r) => !walled.has(r.client_id));
  };
  const find = (request: FixtureRequest): AuditIndexRowOut | undefined =>
    visible(request).find((r) => r.work_item_id === request.params.work_item_id);
  const northwind = rows.find((r) => r.name === "Northwind Robotics 401(k) Plan");
  const docsOf = (row: AuditIndexRowOut) =>
    sourceDocuments(
      row.work_item_id,
      stableId(`binder:${row.engagement_id}:pbc`),
      seed.requestItems[row.engagement_id] ?? [],
      seed.requestOwners,
      today,
    );
  return {
    "GET /v1/audits": (request) => {
      const q = request.query;
      const phase = q.get("phase");
      const segment = q.get("segment");
      const due = q.get("due");
      const search = q.get("q");
      return json(
        auditIndexPage(
          visible(request),
          {
            ...(phase === null ? {} : { phase: phase as AuditEngagementStatus }),
            ...(segment === null ? {} : { segment: segment as Segment }),
            ...(due === null ? {} : { due: due as Due }),
            ...(search === null ? {} : { q: search }),
          },
          today,
        ),
      );
    },
    "GET /v1/audits/{work_item_id}/cockpit": (request) => {
      const row = find(request);
      if (row === undefined || row.work_item_id !== northwind?.work_item_id) {
        return json(NOT_FOUND, 404);
      }
      const docs = docsOf(row);
      return json(
        northwindCockpit(
          {
            workItemId: row.work_item_id,
            engagementId: row.engagement_id,
            clientId: row.client_id,
          },
          grammar,
          docs.received,
          docs.total,
        ),
      );
    },
    "GET /v1/audits/{work_item_id}/source-documents": (request) => {
      const row = find(request);
      return row === undefined ? json(NOT_FOUND, 404) : json(docsOf(row));
    },
  };
}
