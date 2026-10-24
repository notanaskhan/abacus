// F-04-T31 (F-04.21; ADR-085): fixture mode against the fixtures exported from the Python
// scenario through the API (`make fixtures SNAPSHOT=E0`; the backend's equivalence test holds the
// files to `make seed-demo` + the API). Every row the API answers is a row fixture mode serves,
// with the same id and the same value in every field fixture mode sets.
//
// Known gaps, so the interim TS seed is not retired yet (TASK-1161): fixture mode serves rows in
// the TS seed's order (CLI-01's featured clients first; the PBC in handoff order) where the API
// sorts by name and by its own key; it leaves optional request-item fields unset where the API
// answers null or false; and it lists every engagement to every persona where the API lists a
// person's own (Hannah Leclerc: Northwind's EBP audit only).

import { describe, expect, it } from "vitest";
import type { FixtureRequest } from "../../app-core/fixture-mode";
import { seedHandlers } from "../handlers";
import { EXPORTED_E0, type ExportedRead } from "./exported";
import { getSeed } from "./index";

type Row = Record<string, unknown>;

const THIRD_PARTY_ASSIGNEES = 11;

const seed = getSeed();
const handlers = seedHandlers(seed);

async function served(key: string, persona: string, params: Record<string, string> = {}) {
  const handler = handlers[key];
  if (handler === undefined) throw new Error(`no fixture handler for ${key}`);
  const request: FixtureRequest = {
    method: "GET",
    path: key.slice(4),
    params,
    query: new URLSearchParams(),
    body: undefined,
    persona,
  };
  // The TS seed writes instants with milliseconds; the API without.
  const text = JSON.stringify(await (await handler(request)).json()).replace(/\.000Z"/g, 'Z"');
  return JSON.parse(text) as Row[];
}

function idOf(row: Row): string {
  return String(row.id ?? row.client_id);
}

/** The `<id>.<field>` pairs where fixture mode serves a value the API does not answer. */
function divergences(exported: ExportedRead<unknown>, fixture: Row[]): string[] {
  const byId = new Map(fixture.map((r) => [idOf(r), r]));
  const out: string[] = [];
  for (const row of exported.body as Row[]) {
    const mine = byId.get(idOf(row));
    expect(mine, `${exported.request}: ${idOf(row)} is served`).toBeDefined();
    for (const [key, value] of Object.entries(mine ?? {})) {
      if (JSON.stringify(row[key]) !== JSON.stringify(value)) out.push(`${idOf(row)}.${key}`);
    }
  }
  return out.sort();
}

function expectProjection(exported: ExportedRead<unknown>, fixture: Row[]) {
  expect(divergences(exported, fixture)).toEqual([]);
}

describe("the E0 fixtures exported from the scenario", () => {
  it("name the scenario version, the snapshot and the persona they were read as", () => {
    for (const read of Object.values(EXPORTED_E0)) {
      expect(read.scenario.snapshot).toBe("E0");
      expect(read.scenario.version).toMatch(/^bh-/);
      expect(read.persona).not.toBe("");
    }
  });

  it("GET /v1/firm/clients: the same 184 clients, by id and name", async () => {
    const read = EXPORTED_E0.firmClients;
    const fixture = await served(read.request, read.persona);
    expect(fixture).toHaveLength(read.body.length);
    expectProjection(read, fixture);
  });

  it("GET /v1/engagements: every engagement the API lists, as fixture mode serves it", async () => {
    const read = EXPORTED_E0.engagements;
    expectProjection(read, await served(read.request, read.persona));
  });

  it("Northwind's request items: the same 24 items, field for field where fixture mode sets one", async () => {
    const read = EXPORTED_E0.northwindRequestItems;
    const fixture = await served(read.request, read.persona, {
      engagement_id: seed.engagementIds.A1 ?? "",
    });
    expect(fixture).toHaveLength(read.body.length);
    // Known gap (TASK-1161): the TS seed names third-party portal people (Keystone, PayGrid,
    // Harborline, Summit, BrokerWindow) as client assignees; the scenario's load, portal slice
    // included, assigns only the plan's own people. Pinned, so a new drift or a fix both fail.
    const gaps = divergences(read, fixture);
    expect(new Set(gaps.map((g) => g.split(".")[1]))).toEqual(
      new Set(["client_assignee_user_id"]),
    );
    expect(gaps).toHaveLength(THIRD_PARTY_ASSIGNEES);
  });
});
