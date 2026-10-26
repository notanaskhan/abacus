// F-04-T05 · reads of key OpenAPI paths through fixture mode return seed data, shaped as the
// OpenAPI document says, for the persona and clock the scenario names.
import {
  clientContacts,
  firmClients,
  firmMembers,
  getEngagement,
  listEngagements,
  listRequestItems,
  me,
  myCapabilities,
  searchClients,
  staff,
  timeZone,
  workItems,
} from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { nowMs } from "../app-core/clock";
import { defineScenarios, installFixtureMode, json } from "../app-core/fixture-mode";
import { seedHandlers } from "./handlers";
import {
  installSeedFixtures,
  installSeedFromSearch,
  resolveOpens,
  screenScenarioFromSearch,
} from "./install";
import { validateResponse } from "./schema-check";
import { seedScenario } from "./scenario";
import { getSeed } from "./seed";

const seed = getSeed();
const A1 = seed.engagementIds.A1 ?? "";
const FELD = seed.engagementIds.feld ?? "";

let restore: (() => void) | null = null;
let saved: ReturnType<typeof client.getConfig>;
beforeEach(() => {
  saved = client.getConfig();
  client.setConfig({ baseUrl: "http://fixture.test", throwOnError: true });
});
afterEach(() => {
  restore?.();
  restore = null;
  client.setConfig({ baseUrl: saved.baseUrl ?? "", throwOnError: false });
});

describe("the seed scenario", () => {
  it("is a valid fixture-mode scenario at the demo instant, as Hannah Leclerc", () => {
    const scenario = seedScenario();
    expect(scenario).toMatchObject({
      state: "e0",
      persona: "hannah-leclerc",
      clock: "2026-09-14T09:24:00-05:00",
    });
    expect(Object.keys(scenario.handlers)).toContain("GET /v1/engagements/{engagement_id}");
  });

  it("stands the browser clock at 9:24 AM CT on Mon 14 Sep 2026", () => {
    restore = installSeedFixtures();
    expect(nowMs()).toBe(Date.parse("2026-09-14T14:24:00Z"));
  });

  it("lets a screen's own scenario start from it and override one path", async () => {
    const e0 = seedScenario();
    const scenarios = defineScenarios({
      b: {
        ...e0,
        state: "b",
        handlers: { ...e0.handlers, "GET /v1/firm/clients": () => json([]) },
      },
    });
    restore = installFixtureMode(scenarios.b);
    expect((await firmClients()).data).toEqual([]);
    expect((await listEngagements()).data).toHaveLength(28);
  });

  it("answers an unknown route with the fixture 404", async () => {
    restore = installSeedFixtures();
    const result = await client.get({ url: "/v1/firm/no-such", throwOnError: false });
    expect(result.response?.status).toBe(404);
  });
});

describe("reads through the generated client", () => {
  beforeEach(() => {
    restore = installSeedFixtures();
  });

  it("lists the 27 audits and the Feld return, past engagements included", async () => {
    const list = (await listEngagements()).data ?? [];
    expect(list).toHaveLength(28);
    expect(list.filter((e) => e.service_line === "audit")).toHaveLength(27);
    expect(list.map((e) => e.status)).toContain("accepted");
    expect(validateResponse("GET", "/v1/engagements", list)).toEqual([]);
  });

  it("reads one engagement with its gates and team", async () => {
    const result = await getEngagement({ path: { engagement_id: A1 } });
    expect(result.data).toMatchObject({
      name: "PY2025 EBP Audit",
      client_name: "Northwind Robotics, Inc.",
      status: "active",
    });
    expect(result.data?.gates?.map((g) => g.gate)).toEqual(["G1", "G2", "G3"]);
    expect(validateResponse("GET", "/v1/engagements/{engagement_id}", result.data)).toEqual([]);
  });

  it("answers an unknown engagement with 404 not_found", async () => {
    const result = await getEngagement({
      path: { engagement_id: "00000000-0000-4000-8000-000000000000" },
      throwOnError: false,
    });
    expect(result.response?.status).toBe(404);
    expect(result.error).toEqual({ detail: "not_found" });
  });

  it("reads Northwind's PBC list: 24 requests, 11 received", async () => {
    const items = (await listRequestItems({ path: { engagement_id: A1 } })).data ?? [];
    expect(items).toHaveLength(24);
    expect(items.filter((r) => r.status === "received")).toHaveLength(11);
    expect(
      validateResponse("GET", "/v1/engagements/{engagement_id}/request-items", items),
    ).toEqual([]);
  });

  it("reads the Feld binder: 7 requests, 2 open", async () => {
    const items = (await listRequestItems({ path: { engagement_id: FELD } })).data ?? [];
    expect(items).toHaveLength(7);
    expect(items.filter((r) => r.status === "requested")).toHaveLength(2);
  });

  it("reads an assurance work item with its phase", async () => {
    const items = (await workItems({ path: { engagement_id: A1 } })).data ?? [];
    expect(items).toMatchObject([{ kind: "assurance", status: "active", phase: "planning" }]);
    expect(validateResponse("GET", "/v1/engagements/{engagement_id}/work-items", items)).toEqual(
      [],
    );
  });

  it("reads the 184 clients, the 46 seats and the portal contacts", async () => {
    const clients = (await firmClients()).data ?? [];
    expect(clients).toHaveLength(184);
    expect(validateResponse("GET", "/v1/firm/clients", clients)).toEqual([]);
    const people = (await staff()).data;
    expect(people?.members).toHaveLength(46);
    expect(validateResponse("GET", "/v1/firm/staff", people)).toEqual([]);
    expect((await firmMembers()).data).toHaveLength(46);
    const contacts = (await clientContacts({ path: { engagement_id: A1 } })).data ?? [];
    expect(contacts.map((c) => c.display_name)).toEqual(["Dana Kowalski", "Sam Ortiz"]);
    expect(
      validateResponse("GET", "/v1/engagements/{engagement_id}/client-contacts", contacts),
    ).toEqual([]);
    expect((await timeZone()).data).toEqual({ time_zone: "America/Chicago" });
  });

  it("finds a client by name, with its entities", async () => {
    const found = (await searchClients({ query: { q: "northwind" } })).data ?? [];
    expect(found.map((c) => c.name)).toEqual(["Northwind Robotics, Inc."]);
    expect(found[0]?.entities.map((e) => e.name)).toEqual([
      "Northwind Robotics, Inc.",
      "Northwind Robotics 401(k) Plan",
    ]);
    expect(validateResponse("GET", "/v1/firm/clients/search", found)).toEqual([]);
    expect((await searchClients({ query: { q: "Schwab" } })).data).toEqual([]);
  });

  it("reads /v1/me as Hannah Leclerc by default", async () => {
    const result = (await me()).data;
    expect(result).toMatchObject({
      display_name: "Hannah Leclerc",
      email: "hannah.leclerc@brightwaterhale.com",
    });
    expect(result?.memberships[0]).toMatchObject({ firm_name: "Brightwater Hale", kind: "staff" });
    expect(validateResponse("GET", "/v1/me", result)).toEqual([]);
  });
});

describe("personas, clock and latency from the query string", () => {
  it("reads the persona from ?as= and keeps a walled client out for Lena Park", async () => {
    restore = installSeedFromSearch("?as=lena-park");
    expect((await me()).data?.display_name).toBe("Lena Park");
    const clients = (await firmClients()).data ?? [];
    expect(clients).toHaveLength(183);
    expect(clients.some((c) => c.name.startsWith("Ashford"))).toBe(false);
    expect((await searchClients({ query: { q: "ashford" } })).data).toEqual([]);
  });

  it("shows Ashford to a persona who is not walled from it", async () => {
    restore = installSeedFromSearch("?as=grace-holloway");
    expect(((await firmClients()).data ?? []).some((c) => c.name.startsWith("Ashford"))).toBe(
      true,
    );
  });

  it("answers a portal persona as a client member of the firm", async () => {
    restore = installSeedFromSearch("?as=claire-feld");
    expect((await me()).data?.memberships[0]).toMatchObject({ kind: "client", firm_role: null });
  });

  it("refuses an unknown persona loudly rather than falling back", async () => {
    restore = installSeedFromSearch("?as=nobody-here");
    const result = await me({ throwOnError: false });
    expect(result.response?.status).toBe(404);
  });

  it("stands the clock at ?clock= and ignores one it cannot parse", () => {
    restore = installSeedFromSearch("?clock=2026-09-14T09:41:00-05:00");
    expect(nowMs()).toBe(Date.parse("2026-09-14T09:41:00-05:00"));
    restore();
    restore = installSeedFromSearch("?clock=not-a-time");
    expect(nowMs()).toBe(Date.parse("2026-09-14T09:24:00-05:00"));
  });

  it("slows every answer with ?latency=", async () => {
    restore = installSeedFromSearch("?latency=60");
    const started = performance.now();
    await timeZone();
    expect(performance.now() - started).toBeGreaterThanOrEqual(50);
  });
});

describe("handlers", () => {
  it("are keyed by OpenAPI path and METHOD", () => {
    for (const route of Object.keys(seedHandlers())) expect(route).toMatch(/^GET \/v1\//);
  });
});

describe("journey switches: ?flags= and ?scenario= (P-07-T22, P-06-T25)", () => {
  it("?flags= turns the named flags on in the persona's capabilities", async () => {
    restore = installSeedFromSearch("?as=grace-holloway&flags=clients.v2,engagements.v2");
    const flags = (await myCapabilities()).data?.flags ?? {};
    expect(flags["clients.v2"]).toBe(true);
    expect(flags["engagements.v2"]).toBe(true);
  });

  it("leaves capabilities alone without ?flags=", async () => {
    restore = installSeedFromSearch("?as=grace-holloway");
    const caps = await myCapabilities({ throwOnError: false });
    expect(caps.data?.flags["clients.v2"]).toBeUndefined();
  });

  it("?scenario= lays the screen's scenario over the seed, its persona and what it opens", async () => {
    const screen = await screenScenarioFromSearch("?scenario=BND-02:b");
    expect(screen?.scenario.persona).toBe("kevin-osei");
    expect(screen?.opens.binderId).toMatch(/^[0-9a-f-]{36}$/);
    restore = installSeedFromSearch("?scenario=BND-02:b", screen?.scenario);
    expect((await me()).data?.display_name).toBe("Kevin Osei");
  });

  it("refuses a screen or state it has no scenario for", async () => {
    await expect(screenScenarioFromSearch("?scenario=XYZ-99:a")).rejects.toThrow();
    await expect(screenScenarioFromSearch("?scenario=BND-02:zz")).rejects.toThrow();
  });

  it("resolves _key_ tokens in the path and the query, and leaves unknown ones", () => {
    const opens = { binderId: "b1", requestId: "r1" };
    expect(resolveOpens("/binders/_binderId_", opens)).toBe("/binders/b1");
    expect(resolveOpens("/binders/_binderId_?as=kevin-osei", opens)).toBe(
      "/binders/b1?as=kevin-osei",
    );
    expect(resolveOpens("/binders/_binderId_?ov=request%3A_requestId_%3A_binderId_", opens)).toBe(
      "/binders/b1?ov=request%3Ar1%3Ab1",
    );
    expect(resolveOpens("/binders/_binderId_?request=_requestId_&as=x", opens)).toBe(
      "/binders/b1?request=r1&as=x",
    );
    expect(resolveOpens("/binders/_other_", opens)).toBe("/binders/_other_");
  });
});
