// G-02-T11: security-center v1 consumer fixtures for ADM-06 (docs/contracts/security-center.md).
// Typed with the generated client, so a breaking change fails `tsc`, and checked against the
// OpenAPI document at run time. The pytest half is backend/tests/contracts/security_center/.
import { describe, expect, it } from "vitest";
import type {
  FirmExportScheduleOut,
  SecurityIncidentDetailOut,
  SecurityOverviewOut,
} from "@abacus/api-client";
import type { FixtureRequest } from "../../app-core/fixture-mode";
import { securityCenterHandlers } from "../handlers/security-center";
import { scenarios } from "../scenarios/ADM-06";
import { validateResponse } from "../schema-check";
import { INCIDENT_005 } from "../seed/security-center";

function request(
  method: string,
  path: string,
  params: Record<string, string> = {},
  body?: unknown,
  persona = "felix-andersen",
): FixtureRequest {
  return { method, path, params, query: new URLSearchParams(), body, persona };
}

type Handlers = ReturnType<typeof securityCenterHandlers>;

async function call(handlers: Handlers, key: string, req: FixtureRequest) {
  const handler = handlers[key];
  if (handler === undefined) throw new Error(`no handler for ${key}`);
  const response = await handler(req);
  return { status: response.status, body: (await response.json()) as unknown };
}

// Every read the security center serves, with the path parameters its fixture answers.
const READS: [string, Record<string, string>][] = [
  ["/v1/firm/security", {}],
  ["/v1/firm/security/sessions", {}],
  ["/v1/firm/security/posture", {}],
  ["/v1/firm/support-access", {}],
  ["/v1/firm/security/incidents", {}],
  ["/v1/firm/security/incidents/{incident_id}", { incident_id: INCIDENT_005.id }],
  ["/v1/firm/data-exports/schedule", {}],
  ["/v1/firm/safeguards", {}],
];

describe("security-center v1 fixtures (ADM-06)", () => {
  it("serves a to h and T03's states; i and j stay G-03-T29's", () => {
    expect(Object.keys(scenarios).sort()).toEqual([
      "a",
      "b",
      "c",
      "d",
      "d_waiting",
      "e",
      "f",
      "g",
      "h",
      "sessions",
      "support_granted",
      "support_requested",
      "support_revoked",
      "unlock",
    ]);
  });

  it.each(READS)("GET %s matches the OpenAPI document", async (path, params) => {
    const { status, body } = await call(
      securityCenterHandlers(),
      `GET ${path}`,
      request("GET", path, params),
    );
    expect(status).toBe(200);
    expect(validateResponse("GET", path, body)).toEqual([]);
  });

  it("e: the Jan 11 snapshot reads SSO not yet enforced", async () => {
    const { body } = await call(
      securityCenterHandlers({ view: "jan_11" }),
      "GET /v1/firm/security",
      request("GET", "/v1/firm/security"),
    );
    expect((body as SecurityOverviewOut).sign_in.require_sso).toBe(false);
    expect(validateResponse("GET", "/v1/firm/security", body)).toEqual([]);
  });

  it("a longer session is refused 422 policy_loosening_refused; anyone but the QI 403", async () => {
    const handlers = securityCenterHandlers();
    const longer = await call(
      handlers,
      "PUT /v1/firm/security/sign-in",
      request("PUT", "/v1/firm/security/sign-in", {}, { session_absolute_minutes: 1440 }),
    );
    expect(longer.status).toBe(422);
    expect(longer.body).toMatchObject({ detail: "policy_loosening_refused" });
    const margaret = await call(
      handlers,
      "PUT /v1/firm/security/sign-in",
      request("PUT", "/v1/firm/security/sign-in", {}, {}, "margaret-okonkwo"),
    );
    expect(margaret.status).toBe(403);
  });

  it("d_waiting: Felix's decision waits for a second, distinct decider", async () => {
    const path = "/v1/firm/security/incidents/{incident_id}";
    const { body } = await call(
      securityCenterHandlers({ waiting: true }),
      `GET ${path}`,
      request("GET", path, { incident_id: INCIDENT_005.id }),
    );
    const detail = body as SecurityIncidentDetailOut;
    expect(detail.pending_decision).toBeTruthy();
    expect(validateResponse("GET", path, body)).toEqual([]);
  });

  it("the schedule reads its approvals and validates", async () => {
    const path = "/v1/firm/data-exports/schedule";
    const { body } = await call(securityCenterHandlers(), `GET ${path}`, request("GET", path));
    const schedule = body as FirmExportScheduleOut;
    expect(Array.isArray(schedule.approvals)).toBe(true);
    expect(validateResponse("GET", path, body)).toEqual([]);
  });
});
