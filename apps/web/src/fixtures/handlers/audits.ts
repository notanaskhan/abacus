// The audits family routes over the seed in fixture mode (A-01-T06; docs/contracts/audits-cockpit.md):
// the AUD-01 index, Northwind's AUD-02 cockpit and the Source Documents aggregate. Typed with the
// generated client. A walled client's audits are absent from the index and answer 404 elsewhere
// (INV-3, DEC-43: no hidden count); a work item without a cockpit fixture answers 404. The rail
// grammar (run, idle, pills) is the scenario's choice; the seed's clock is the day.

import type {
  ActivityOut,
  AgentRunOut,
  AgentOut,
  AuditEngagementStatus,
  AuditIndexRowOut,
} from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import { DEFAULT_PERSONA } from "../handlers";
import type { Seed } from "../seed";
import { type CockpitGrammar, northwindCockpit } from "../seed/audit-cockpit";
import {
  E0_SEGMENTS,
  E2_SEGMENTS,
  type SourceSort,
  auditIndexPage,
  auditIndexRows,
  sortAuditRows,
  sourceDocuments,
  wave7Rows,
} from "../seed/audits-index";
import { stableId } from "../seed/prng";

const NOT_FOUND = { detail: "not_found" };
type Segment = AuditIndexRowOut["segment"];
type Due = "any" | "7d" | "14d" | "30d";

export interface AuditHandlerOptions {
  /** E2: the wave-7 view (AUD-01 g, h): A28–A33 and the SOC & IT and Internal audit segments. */
  epoch?: "E0" | "E2";
  /** The Agent tab's v1 activity (AUD-02; DV-2); empty when absent. */
  activity?: readonly ActivityOut[];
  /** The dock's run thread (P-09-T09); empty when absent. */
  agentRuns?: readonly AgentRunOut[];
}

export function auditHandlers(
  seed: Seed,
  grammar: CockpitGrammar = "run",
  options: AuditHandlerOptions = {},
): Record<string, FixtureHandler> {
  const today = new Date(seed.clock.ms).toISOString().slice(0, 10);
  const e2 = options.epoch === "E2";
  const clientIdOf = (name: string): string => {
    const seeded = seed.clients.find((c) => c.name === name);
    return stableId(seeded === undefined ? `client:wave7:${name}` : `client:${seeded.slug}`);
  };
  const rows = sortAuditRows([
    ...auditIndexRows(seed.engagements, seed.workItems, today),
    ...(e2 ? wave7Rows(today, clientIdOf) : []),
  ]);
  const visible = (request: FixtureRequest): AuditIndexRowOut[] => {
    const who = request.persona ?? DEFAULT_PERSONA;
    const walled = new Set(seed.walls.filter((w) => w.personSlug === who).map((w) => w.clientId));
    return rows.filter((r) => !walled.has(r.client_id));
  };
  const find = (request: FixtureRequest): AuditIndexRowOut | undefined =>
    visible(request).find((r) => r.work_item_id === request.params.work_item_id);
  const northwind = rows.find((r) => r.name === "Northwind Robotics 401(k) Plan");
  const docsOf = (row: AuditIndexRowOut, sort: SourceSort = "missing_first") =>
    sourceDocuments(
      row.work_item_id,
      stableId(`binder:${row.engagement_id}:pbc`),
      seed.requestItems[row.engagement_id] ?? [],
      seed.requestOwners,
      today,
      sort,
    );
  // The engagement agent on Northwind (SPEC-027; AUD-02 Agent tab): pause and resume as the caller.
  let agent: AgentOut = {
    enabled: true,
    paused_at: null,
    paused_by: null,
    reason: null,
    firm_paused_at: null,
  };
  const nameOf = (request: FixtureRequest): string =>
    seed.people.find((p) => p.slug === (request.persona ?? DEFAULT_PERSONA))?.name ?? "";
  const northwindEngagement = (request: FixtureRequest): boolean =>
    northwind !== undefined &&
    request.params.engagement_id === northwind.engagement_id &&
    find({ ...request, params: { work_item_id: northwind.work_item_id } }) !== undefined;
  return {
    "GET /v1/audits": (request) => {
      const q = request.query;
      const phase = q.get("phase");
      const segment = q.get("segment");
      const due = q.get("due");
      const search = q.get("q");
      const type = q.get("type");
      const office = q.get("office");
      return json(
        auditIndexPage(
          visible(request),
          {
            ...(phase === null ? {} : { phase: phase as AuditEngagementStatus }),
            ...(segment === null ? {} : { segment: segment as Segment }),
            ...(due === null ? {} : { due: due as Due }),
            ...(search === null ? {} : { q: search }),
            ...(type === null ? {} : { type: type as AuditIndexRowOut["engagement_type"] }),
            ...(office === null ? {} : { office }),
          },
          today,
          e2 ? E2_SEGMENTS : E0_SEGMENTS,
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
      const sort = request.query.get("sort") === "received_first" ? "received_first" : undefined;
      return row === undefined ? json(NOT_FOUND, 404) : json(docsOf(row, sort));
    },
    "GET /v1/engagements/{engagement_id}/agent": (request) =>
      northwindEngagement(request) ? json(agent) : json(NOT_FOUND, 404),
    "GET /v1/engagements/{engagement_id}/activity": (request) =>
      northwindEngagement(request) ? json(options.activity ?? []) : json(NOT_FOUND, 404),
    // P-09-T09: the dock's run thread; no runs unless a scenario scripts them.
    "GET /v1/engagements/{engagement_id}/agent-runs": (request) =>
      northwindEngagement(request) ? json(options.agentRuns ?? []) : json(NOT_FOUND, 404),
    "POST /v1/engagements/{engagement_id}/agent/pause": (request) => {
      if (!northwindEngagement(request)) return json(NOT_FOUND, 404);
      agent = {
        ...agent,
        paused_at: new Date(seed.clock.ms).toISOString(),
        paused_by: nameOf(request),
      };
      return json(agent);
    },
  };
}

/** Northwind's PY2025 EBP audit work item: the AUD-02 and AUD-03 artboards' `$auditId`. */
export function northwindAuditId(seed: Seed): string {
  const today = new Date(seed.clock.ms).toISOString().slice(0, 10);
  const row = auditIndexRows(seed.engagements, seed.workItems, today).find(
    (r) => r.name === "Northwind Robotics 401(k) Plan",
  );
  if (row === undefined) throw new Error("the seed has no Northwind audit");
  return row.work_item_id;
}
