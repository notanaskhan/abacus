// G-02-T04: audit-log v1 consumer fixtures for ADM-07 a to g (docs/contracts/audit-log.md).
// Typed with the generated client, so a breaking change fails `tsc`, and checked against the
// OpenAPI document at run time. The pytest half is backend/tests/contracts/audit_log/.
import { describe, expect, it } from "vitest";
import type { AuditEventDetail, AuditEventPageOut, AuditExport } from "@abacus/api-client";
import type { FixtureRequest } from "../../app-core/fixture-mode";
import { auditLogHandlers } from "../handlers/audit-log";
import { scenarios } from "../scenarios/ADM-07";
import { validateResponse } from "../schema-check";
import {
  AUDIT_TOTAL,
  COPPERLEAF_SEQ,
  EMPTY_SEARCH,
  VIA_AGENT_TOTAL,
  feed,
} from "../seed/audit-log";

function request(
  method: string,
  path: string,
  params: Record<string, string> = {},
  query = "",
  persona = "felix-andersen",
): FixtureRequest {
  return {
    method,
    path,
    params,
    query: new URLSearchParams(query),
    body: undefined,
    persona,
  };
}

type Handlers = ReturnType<typeof auditLogHandlers>;

async function call(handlers: Handlers, key: string, req: FixtureRequest) {
  const handler = handlers[key];
  if (handler === undefined) throw new Error(`no handler for ${key}`);
  const response = await handler(req);
  return { status: response.status, body: (await response.json()) as unknown };
}

async function callPage(handlers: Handlers, key: string, req: FixtureRequest) {
  const { status, body } = await call(handlers, key, req);
  return { status, body: body as AuditEventPageOut };
}

async function callDetail(handlers: Handlers, key: string, req: FixtureRequest) {
  const { status, body } = await call(handlers, key, req);
  return { status, body: body as AuditEventDetail };
}

async function callExport(handlers: Handlers, key: string, req: FixtureRequest) {
  const { status, body } = await call(handlers, key, req);
  return { status, body: body as AuditExport };
}

const LIST = "GET /v1/audit-events";

describe("audit-log v1 fixtures (ADM-07)", () => {
  it("serves a scenario for every artboard, d fixture-only", () => {
    expect(Object.keys(scenarios).sort()).toEqual([
      "a",
      "b",
      "c",
      "c_withheld",
      "d",
      "e",
      "f",
      "g",
    ]);
  });

  it("a: 14 rows newest first, 18,406 events, no policy events, Load more", async () => {
    const { body } = await callPage(auditLogHandlers(), LIST, request("GET", "/v1/audit-events"));
    expect(body.items).toHaveLength(14);
    expect(body.total).toBe(AUDIT_TOTAL);
    expect(body.counts?.policy).toBe(0);
    expect(body.next_cursor).not.toBeNull();
    const seqs = body.items.map((r) => r.seq);
    expect([...seqs].sort((x, y) => y - x)).toEqual(seqs);
    expect(validateResponse("GET", "/v1/audit-events", body)).toEqual([]);
  });

  it("b: via Agent lists rows 6, 9, 11 and 14 only, 4 of 1,962, each naming its person", async () => {
    const { body } = await callPage(
      auditLogHandlers(),
      LIST,
      request("GET", "/v1/audit-events", {}, "actor_kind=via_agent"),
    );
    expect(body.items.map((r) => AUDIT_TOTAL - r.seq + 1)).toEqual([6, 9, 11, 14]);
    expect(body.total).toBe(VIA_AGENT_TOTAL);
    for (const row of body.items) expect(row.actor.on_behalf_of?.display_name).toBeTruthy();
  });

  it("no row names the agent as an approver (INV-1, INV-5)", () => {
    for (const row of [...feed("default"), ...feed("policy")]) {
      if (row.mark === "ok") expect(row.actor.kind).not.toBe("via_agent");
    }
  });

  it("c: Margaret reads the Copperleaf values, 20,020.00, with 14,900.00 left out for Priya Raman", async () => {
    const { body } = await callDetail(
      auditLogHandlers(),
      "GET /v1/audit-events/{seq}",
      request(
        "GET",
        `/v1/audit-events/${String(COPPERLEAF_SEQ)}`,
        { seq: String(COPPERLEAF_SEQ) },
        "",
        "margaret-okonkwo",
      ),
    );
    expect(body.values.status).toBe("resolved");
    const cents = body.values.rows?.reduce((n, r) => n + Math.round(Number(r.amount) * 100), 0);
    expect(cents).toBe(2_002_000);
    expect(body.values.not_included?.[0]?.amount).toBe("14900.00");
    expect(body.values.not_included?.[0]?.routed_to?.display_name).toBe("Priya Raman");
    expect(body.session?.auth_method).toBe("sso");
    expect(body.device_label).toBe("Chrome · macOS");
    expect(validateResponse("GET", "/v1/audit-events/{seq}", body)).toEqual([]);
  });

  it("c, Felix's variant: metadata only, values withheld for need to know", async () => {
    const { body } = await callDetail(
      auditLogHandlers(),
      "GET /v1/audit-events/{seq}",
      request("GET", `/v1/audit-events/${String(COPPERLEAF_SEQ)}`, {
        seq: String(COPPERLEAF_SEQ),
      }),
    );
    expect(body.values).toMatchObject({ status: "withheld", reason: "need_to_know", rows: [] });
  });

  it("d: the policy's acceptance and Priya Raman's reversal replace row 4; 2 policy events", async () => {
    const { body } = await callPage(
      auditLogHandlers("policy"),
      LIST,
      request("GET", "/v1/audit-events"),
    );
    expect(body.counts?.policy).toBe(2);
    const policy = body.items.filter((r) => r.actor.kind === "policy");
    expect(policy.map((r) => r.actor.policy_ref)).toEqual(["BH AJE thresholds v2"]);
    expect(
      body.items.some((r) => r.mark === "no" && r.actor.person?.display_name === "Priya Raman"),
    ).toBe(true);
  });

  it("e → g: the export answers 202 and is ready with its file and manifest", async () => {
    const handlers = auditLogHandlers();
    const posted = await callExport(
      handlers,
      "POST /v1/audit-events/exports",
      request("POST", "/v1/audit-events/exports"),
    );
    expect(posted.status).toBe(202);
    expect(posted.body.file_name).toBe("audit-log-2026-09-08-2026-09-14.csv");
    expect(posted.body.include_values).toBe(true);
    const read = await callExport(
      handlers,
      "GET /v1/audit-events/exports/{export_id}",
      request("GET", "", { export_id: posted.body.id }),
    );
    expect(read.body.status).toBe("ready");
    expect(validateResponse("GET", "/v1/audit-events/exports/{export_id}", read.body)).toEqual([]);
  });

  it("f: a search for pell street iii finds nothing", async () => {
    const { body } = await callPage(
      auditLogHandlers(),
      LIST,
      request("GET", "/v1/audit-events", {}, `q=${encodeURIComponent(EMPTY_SEARCH)}`),
    );
    expect(body.items).toEqual([]);
    expect(body.total).toBe(0);
  });

  it("an IP click filters to that IP; since_seq lists newer events oldest first", async () => {
    const byIp = await callPage(
      auditLogHandlers(),
      LIST,
      request("GET", "/v1/audit-events", {}, "ip=198.51.100.44"),
    );
    expect(byIp.body.items.map((r) => r.action)).toEqual(["pii.revealed", "tax_return.exported"]);
    const since = await callPage(
      auditLogHandlers(),
      LIST,
      request("GET", "/v1/audit-events", {}, `since_seq=${String(AUDIT_TOTAL - 2)}`),
    );
    expect(since.body.items.map((r) => r.seq)).toEqual([AUDIT_TOTAL - 1, AUDIT_TOTAL]);
  });

  it("agent and system rows carry no request context", () => {
    for (const row of feed("default")) {
      if (row.actor.kind !== "person") expect(row.ip ?? null).toBeNull();
    }
  });
});
