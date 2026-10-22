// P-01-T07: SHL-03 has a scenario for every artboard (a–f), each seen as its README viewer at
// Mon 14 Sep 2026, 9:24 AM CT, answering /v1/me v3, the capability nav and the office PUT.
import { describe, expect, it } from "vitest";
import type { Scenario } from "../../app-core/fixture-mode";
import type { CapabilitiesOut, MeOut } from "@abacus/api-client";
import { officeIdOf } from "../seed/shell";
import { scenarios } from "./SHL-03";

async function call<T>(
  scenario: Scenario,
  route: string,
  body: unknown = null,
): Promise<T & { status?: number }> {
  const handler = scenario.handlers[route];
  if (handler === undefined) throw new Error(`no ${route}`);
  const response = await handler({
    method: route.split(" ")[0] ?? "GET",
    path: route,
    params: {},
    query: new URLSearchParams(),
    body,
    persona: scenario.persona,
  });
  return { ...((await response.json()) as T), status: response.status };
}

describe("SHL-03 scenarios", () => {
  it("cover a–f with the README viewers at 9:24 AM CT", () => {
    expect(Object.fromEntries(Object.entries(scenarios).map(([k, s]) => [k, s.persona]))).toEqual({
      a: "grace-holloway",
      b: "hannah-leclerc",
      c: "daniel-reyes",
      d: "felix-andersen",
      e: "grace-holloway",
      f: "grace-holloway",
    });
    for (const s of Object.values(scenarios)) expect(s.clock).toBe("2026-09-14T09:24:00-05:00");
  });

  it("e: Grace holds the training sandbox membership", async () => {
    const me = await call<MeOut>(scenarios.e, "GET /v1/me");
    expect(me.memberships.map((m) => m.firm_name)).toEqual([
      "Brightwater Hale",
      "Brightwater Hale LLP — Training sandbox",
    ]);
  });

  it("c: Daniel's nav is Firm settings read and Audit log", async () => {
    const caps = await call<CapabilitiesOut>(scenarios.c, "GET /v1/me/capabilities");
    expect(caps.nav).toMatchObject({
      firm_settings: "read",
      audit_log: "read",
      users_roles: "none",
    });
  });

  it("f: picking Chicago stores it and /v1/me reads it back; a foreign office is 404", async () => {
    const chicago = officeIdOf("Chicago");
    const put = await call<{ default_office_id: string | null }>(
      scenarios.f,
      "PUT /v1/me/preferences",
      { default_office_id: chicago },
    );
    expect(put.default_office_id).toBe(chicago);
    expect((await call<MeOut>(scenarios.f, "GET /v1/me")).default_office_id).toBe(chicago);
    const refused = await call(scenarios.f, "PUT /v1/me/preferences", {
      default_office_id: "00000000-0000-4000-8000-000000000000",
    });
    expect(refused.status).toBe(404);
  });

  it("b: Hannah's default office is Chicago before anything is picked", async () => {
    const me = await call<MeOut>(scenarios.b, "GET /v1/me");
    expect(me.default_office_id).toBe(officeIdOf("Chicago"));
  });
});
