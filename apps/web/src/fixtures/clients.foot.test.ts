// P-07-T11 seed footing (docs/screens/CLI-01.md, Figures; P-07 §5 "Seed figures that must foot"):
// the CLI-01 figures from the Brightwater Hale seed through the clients and engagements handlers,
// never restated. Figures foot as integers; no float arithmetic.
import type {
  ClientRowOut,
  EngagementIndexPage,
  ListPageClientRowOut,
  RequestItemOut,
} from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import type { FixtureRequest } from "../app-core/fixture-mode";
import { clientRows, clientsPage } from "./handlers/clients";
import { engagementIndexPage } from "./handlers/engagements";
import { getSeed } from "./seed";
import { COPPERLEAF_CLOSE, NAMED_ROW_FACTS } from "./seed/client-rows";

const seed = getSeed();
const rows = clientRows(seed);
/** Clients with an audit service line at E0: the 3 named and the §9.7 roster's audit clients. */
const AUDIT_CLIENTS = 25;

function request(query: Record<string, string>, persona = "grace-holloway"): FixtureRequest {
  return {
    method: "GET",
    path: "/v1/clients",
    params: {},
    query: new URLSearchParams(query),
    body: null,
    persona,
  };
}

function page(query: Record<string, string>, persona?: string): ListPageClientRowOut {
  return clientsPage(seed, rows, request(query, persona));
}

function row(name: string): ClientRowOut {
  const found = rows.find((r) => r.name === name);
  if (found === undefined) throw new Error(`no row ${name}`);
  return found;
}

function requestsOf(clientName: string): RequestItemOut[] {
  const ids = seed.engagements.filter((e) => e.client_name === clientName).map((e) => e.id);
  return ids.flatMap((id) => seed.requestItems[id] ?? []);
}

describe("CLI-01 footing on the seed", () => {
  it("184 clients at E0 (DEC-47): 16 named + 66 roster + 102 filler", () => {
    const a = page({ status: "active", sort: "last_activity", limit: "16" });
    expect(a.total).toBe(184);
    expect(a.counts?.active).toBe(184);
    expect(Object.keys(NAMED_ROW_FACTS)).toHaveLength(16);
    expect(rows.filter((r) => r.descriptor != null)).toHaveLength(16);
  });

  it("the first page is the 16 named clients, newest activity first, with a next cursor", () => {
    const a = page({ status: "active", sort: "last_activity", limit: "16" });
    expect(a.items.map((r) => r.name)).toEqual([
      "Jonah & Claire Feld",
      "Copperleaf Coffee Roasters, Inc.",
      "Meera Shah",
      "Northwind Robotics, Inc.",
      "Ridgeline Property Partners, LP",
      "Granite Peak Outdoor Supply, Inc.",
      "Harborview Dental Properties, LP",
      "Marcus & Dana Whitley",
      "Walter Thornbury",
      "Bluestem Analytics, LLC",
      "Lakeshore Literacy Alliance",
      "Elena Varga",
      "Calloway Family Trust",
      "Ashford Manufacturing Co.",
      "Juniper & Oak Interiors, LLC",
      "Daniel & Ruth Okafor",
    ]);
    expect(a.next_cursor).not.toBeNull();
    const second = page({ status: "active", limit: "16", cursor: a.next_cursor ?? "" });
    expect(second.items).toHaveLength(16);
    expect(second.items.some((r) => a.items.some((x) => x.id === r.id))).toBe(false);
  });

  it("Northwind's 13 open requests = 24 − 11 received", () => {
    const list = requestsOf("Northwind Robotics, Inc.");
    const received = list.filter((r) => r.status === "received").length;
    expect(list.length).toBe(24);
    expect(received).toBe(11);
    expect(row("Northwind Robotics, Inc.").open_request_count).toBe(list.length - received);
    expect(row("Northwind Robotics, Inc.").open_request_count).toBe(13);
  });

  it("Ridgeline 5, Feld 2 (two open portal requests), Copperleaf 2 = 9 − 7", () => {
    expect(row("Ridgeline Property Partners, LP").open_request_count).toBe(5);
    const feld = requestsOf("Jonah & Claire Feld");
    const satisfied = feld.filter((r) => r.status === "received").length;
    expect(feld.length - satisfied).toBe(2);
    expect(row("Jonah & Claire Feld").open_request_count).toBe(2);
    expect(row("Copperleaf Coffee Roasters, Inc.").open_request_count).toBe(
      COPPERLEAF_CLOSE.requests - COPPERLEAF_CLOSE.received,
    );
    expect(row("Copperleaf Coffee Roasters, Inc.").open_request_count).toBe(2);
  });

  it("Granite Peak reads Binder draft: only draft requests exist, and drafts are not open", () => {
    expect(
      requestsOf("Granite Peak Outdoor Supply, Inc.").every((r) => r.status === "draft"),
    ).toBe(true);
    expect(row("Granite Peak Outdoor Supply, Inc.").binder_draft_only).toBe(true);
    expect(row("Granite Peak Outdoor Supply, Inc.").open_request_count).toBeNull();
  });

  it("entities: Northwind 2, Granite Peak 2, Thornbury 2; every other named client 1", () => {
    const two = new Set([
      "Northwind Robotics, Inc.",
      "Granite Peak Outdoor Supply, Inc.",
      "Walter Thornbury",
    ]);
    const first = page({ status: "active", limit: "16" }).items;
    for (const r of first) expect(r.entity_count, r.name).toBe(two.has(r.name) ? 2 : 1);
  });

  it("Attest only on Northwind, Granite Peak and Lakeshore among the named; Thornbury Invited", () => {
    const first = page({ status: "active", limit: "16" }).items;
    expect(first.filter((r) => r.is_attest_client).map((r) => r.name)).toEqual([
      "Northwind Robotics, Inc.",
      "Granite Peak Outdoor Supply, Inc.",
      "Lakeshore Literacy Alliance",
    ]);
    expect(row("Walter Thornbury").portal_status).toBe("invited");
  });

  it("b: Service line │ Audit among the named is Northwind, Granite Peak and Lakeshore", () => {
    const b = page({ status: "active", service_line: "audit", limit: "16" });
    expect(b.items.slice(0, 3).map((r) => r.name)).toEqual([
      "Northwind Robotics, Inc.",
      "Granite Peak Outdoor Supply, Inc.",
      "Lakeshore Literacy Alliance",
    ]);
    // The handoff's "Showing 3" counted its 16-row sample; the seed's audit clients include the
    // §9.7 roster's audits, so the header reads the seed's count (docs/screens/CLI-01.md, gaps).
    const audit = seed.clients.filter((c) => c.services.includes("audit")).length;
    expect(b.total).toBe(audit);
    expect(b.total).toBe(AUDIT_CLIENTS);
  });

  it("c: for Lena Park, Ashford is absent and total is 183 = 184 − 1, with the same keys", () => {
    const grace = page({ status: "active", limit: "16", facets: "true" });
    const lena = page({ status: "active", limit: "16", facets: "true" }, "lena-park");
    expect(lena.total).toBe(183);
    expect(lena.items.some((r) => r.name === "Ashford Manufacturing Co.")).toBe(false);
    expect(Object.keys(lena).sort()).toEqual(Object.keys(grace).sort());
    expect(JSON.stringify(lena)).not.toMatch(/hidden|wall/i);
    const ids = page({ status: "active", limit: "200" }, "lena-park").items.map((r) => r.name);
    expect(ids).not.toContain("Ashford Manufacturing Co.");
  });

  it("d: Schwab matches no client, entity or contact", () => {
    expect(page({ status: "active", q: "Schwab" }).total).toBe(0);
  });

  it("no row carries a TIN field", () => {
    for (const r of rows) {
      expect(
        Object.keys(r).some((k) => /tin|ssn|ein/.test(k)),
        r.name,
      ).toBe(false);
    }
  });
});

describe("the engagements index over the seed", () => {
  it("segments and tiles sum to the total, and a walled client's engagements are absent", () => {
    const index = (persona: string): EngagementIndexPage =>
      engagementIndexPage(seed, { ...request({}, persona), path: "/v1/engagements/index" });
    const all = index("grace-holloway");
    const segments = (all.facets?.service_line ?? []).reduce((sum, f) => sum + f.n, 0);
    const tiles = Object.values(all.counts ?? {}).reduce((sum, n) => sum + n, 0);
    expect(segments).toBe(all.total);
    expect(tiles).toBe(all.total);
    expect(all.total).toBe(275); // ENG-01a (P-07-T27): 17 named rows and 258 counted
  });
});
