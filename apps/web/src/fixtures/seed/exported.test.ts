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
import { feldOpenUploads } from "../scenarios/POR-02";
import { BINDER_ROWS, toBinderRow } from "./binders";
import { EXPORTED_E0, type ExportedRead } from "./exported";
import { getSeed } from "./index";
import { claireHome } from "./portal-home";

type Row = Record<string, unknown>;

const THIRD_PARTY_ASSIGNEES = 11;
// The Feld binder's fields where the BND-01 fixture and the load differ (TASK-1161): ids (slug
// against label), the preparer (KO in BND-01; none in the load) and the actions (BINDER_ACTIONS
// against the reader's own).
const FELD_BINDER_GAPS = ["allowed_actions", "id", "preparer_user_id", "work_item_id"];
// Claire's home where POR-02 a and the load differ (TASK-1161): every section but the notices
// and the K-1s, which both leave empty.
const PORTAL_HOME_GAPS = [
  "binder",
  "earlier",
  "first_visit",
  "recent_threads",
  "scope",
  "team",
  "todos",
  "welcome_dismissed",
  "work_cards",
];

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

  it("GET /v1/binders: Daniel Reyes's one TY2025 binder is BND-01's Feld row", () => {
    const read = EXPORTED_E0.binders;
    expect(read.body.total).toBe(1);
    expect(read.body.counts).toEqual({
      draft: 0,
      published: 1,
      unpublished: 0,
      complete: 0,
      closed: 0,
    });
    const feld = BINDER_ROWS.find((r) => r.client === "Jonah & Claire Feld");
    if (feld === undefined) throw new Error("no Feld row in the TS seed");
    const fixture = JSON.parse(
      JSON.stringify(toBinderRow(seed, feld)).replace(/\.000Z"/g, 'Z"'),
    ) as Row;
    const api = read.body.items[0] as unknown as Row;
    expect([api.client_name, api.part]).toEqual([fixture.client_name, fixture.part]);
    const differ = Object.keys(fixture)
      .filter((key) => JSON.stringify(api[key]) !== JSON.stringify(fixture[key]))
      .sort();
    // Known gaps (TASK-1161), pinned so a new drift or a fix both fail: the TS seed derives the
    // binder's ids from the client slug where the load derives them from the scenario's labels,
    // and the fixture fields below differ from what the load holds.
    expect(differ).toEqual(FELD_BINDER_GAPS);
  });

  it("GET /v1/portal/home: Claire Feld's home is POR-02 a's, field for field where they agree", () => {
    const read = EXPORTED_E0.portalHome;
    const fixture = claireHome(feldOpenUploads()) as unknown as Row;
    const api = read.body as unknown as Row;
    const differ = Object.keys(fixture)
      .filter((key) => JSON.stringify(api[key]) !== JSON.stringify(fixture[key]))
      .sort();
    // Known gaps (TASK-1161), pinned so a new drift or a fix both fail: POR-02 a reads the Feld
    // binder as 19 of 21 (SPEC-320 AC-15) where the load holds BND-02's 5 of 7, and the fixture's
    // scope ids, team, threads and cards are the TS seed's where the load writes its own.
    expect(differ).toEqual(PORTAL_HOME_GAPS);
  });
});
