// G-02-T15: AI-policy v1 consumer fixtures for ADM-04 (docs/contracts/ai-policy.md). Typed with
// the generated client, so a breaking change fails `tsc`, and checked against the OpenAPI
// document at run time. The pytest half is backend/tests/contracts/ai_policy/.
import { describe, expect, it } from "vitest";
import type { AiPolicyOut, AiPolicyVersionPageOut } from "@abacus/api-client";
import type { FixtureRequest } from "../../app-core/fixture-mode";
import { aiPolicyHandlers } from "../handlers/ai-policy";
import { scenarios } from "../scenarios/ADM-04";
import { validateResponse } from "../schema-check";
import { SECTIONS_V3 } from "../seed/ai-policy";
import { DANIEL, MARGARET } from "../seed/governance";

function request(
  method: string,
  path: string,
  params: Record<string, string> = {},
  body?: unknown,
  persona = "margaret-okonkwo",
  query = new URLSearchParams(),
): FixtureRequest {
  return { method, path, params, query, body, persona };
}

type Handlers = ReturnType<typeof aiPolicyHandlers>;

async function call(handlers: Handlers, key: string, req: FixtureRequest) {
  const handler = handlers[key];
  if (handler === undefined) throw new Error(`no handler for ${key}`);
  const response = await handler(req);
  return { status: response.status, body: (await response.json()) as unknown };
}

const POLICY = "/v1/firm/ai-policy";

describe("ai-policy v1 fixtures (ADM-04)", () => {
  it("serves a, b, d, e, g, h, i and j with the band, awaiting approval and the real firm", () => {
    expect(Object.keys(scenarios).sort()).toEqual([
      "a",
      "awaiting",
      "b",
      "band",
      "d",
      "e",
      "g",
      "h",
      "i",
      "j",
      "real_firm",
    ]);
  });

  it.each(["a", "b", "g", "read_only", "band", "awaiting", "real_firm"] as const)(
    "GET the policy (%s) matches the OpenAPI document",
    async (view) => {
      const { status, body } = await call(
        aiPolicyHandlers({ view }),
        `GET ${POLICY}`,
        request("GET", POLICY),
      );
      expect(status).toBe(200);
      expect(validateResponse("GET", POLICY, body)).toEqual([]);
    },
  );

  it("a: v3 published by Margaret, approved by Daniel; twelve gates, rows 1 and 5 Off + Lock", async () => {
    const { body } = await call(aiPolicyHandlers(), `GET ${POLICY}`, request("GET", POLICY));
    const policy = body as AiPolicyOut;
    expect(policy.effective.version_no).toBe(3);
    expect(policy.effective.requested_by?.display_name).toBe("Margaret Okonkwo");
    expect(policy.effective.approver?.display_name).toBe("Daniel Reyes");
    expect(policy.draft?.differs).toBe(false);
    expect(policy.gates).toHaveLength(12);
    const offered = policy.gates.filter((g) => g.policy_acceptance_available);
    expect(offered.map((g) => g.row)).toEqual([1, 5]);
    expect(
      offered.every((g) => g.policy_acceptance_on === false && g.policy_acceptance_locked),
    ).toBe(true);
    expect(policy.sub_processors.map((s) => s.name)).toEqual(["Amazon Web Services (Bedrock)"]);
  });

  it("b: Override tolerance 8% → 6% is unsaved", async () => {
    const { body } = await call(
      aiPolicyHandlers({ view: "b" }),
      `GET ${POLICY}`,
      request("GET", POLICY),
    );
    const draft = (body as AiPolicyOut).draft;
    expect(draft?.differs).toBe(true);
    expect(draft?.diff).toEqual([
      { path: "governance.override_tolerance_pct", before: "8", after: "6" },
    ]);
  });

  it("a draft that turns the policy principal on is refused 422 with the cell's path", async () => {
    const path = `${POLICY}/draft`;
    const loosened = { ...SECTIONS_V3, policy_principal: { on: true } };
    const { status, body } = await call(
      aiPolicyHandlers(),
      `PUT ${path}`,
      request("PUT", path, {}, { sections: loosened }),
    );
    expect(status).toBe(422);
    expect(body).toEqual({
      detail: "policy_loosening_refused",
      facts: { field: "policy_principal.on" },
    });
  });

  it("d → awaiting → g: Margaret publishes for Daniel, who approves; she can't approve", async () => {
    const handlers = aiPolicyHandlers({ view: "b" });
    const own = await call(
      handlers,
      `POST ${POLICY}/versions`,
      request(
        "POST",
        `${POLICY}/versions`,
        {},
        {
          effective_from: "2026-09-15",
          approver_user_id: MARGARET.user_id,
        },
      ),
    );
    expect(own.status).toBe(409);
    const requested = await call(
      handlers,
      `POST ${POLICY}/versions`,
      request(
        "POST",
        `${POLICY}/versions`,
        {},
        {
          effective_from: "2026-09-15",
          approver_user_id: DANIEL.user_id,
        },
      ),
    );
    expect(requested.status).toBe(201);
    const approve = `${POLICY}/versions/{version_no}/approve`;
    const self = await call(
      handlers,
      `POST ${approve}`,
      request("POST", approve, { version_no: "4" }),
    );
    expect(self.status).toBe(409);
    const approved = await call(
      handlers,
      `POST ${approve}`,
      request("POST", approve, { version_no: "4" }, undefined, "daniel-reyes"),
    );
    expect(approved.status).toBe(200);
    expect(validateResponse("POST", approve, approved.body)).toEqual([]);
  });

  it("j: the history lists v3, v2, v1 and validates", async () => {
    const path = `${POLICY}/versions`;
    const { body } = await call(aiPolicyHandlers(), `GET ${path}`, request("GET", path));
    expect((body as AiPolicyVersionPageOut).items.map((v) => v.version_no)).toEqual([3, 2, 1]);
    expect(validateResponse("GET", path, body)).toEqual([]);
    const one = `${POLICY}/versions/{version_no}`;
    const detail = await call(
      aiPolicyHandlers(),
      `GET ${one}`,
      request("GET", one, { version_no: "3" }),
    );
    expect(validateResponse("GET", one, detail.body)).toEqual([]);
  });

  it("the effective read: Auto mode off for audits, and off everywhere on a real firm", async () => {
    const path = `${POLICY}/effective`;
    const synthetic = await call(
      aiPolicyHandlers(),
      `GET ${path}`,
      request(
        "GET",
        path,
        {},
        undefined,
        "margaret-okonkwo",
        new URLSearchParams({ engagement_type: "tax_return" }),
      ),
    );
    expect(validateResponse("GET", path, synthetic.body)).toEqual([]);
    expect(synthetic.body).toMatchObject({ auto_mode: true, auto_mode_effective: true });
    const real = await call(
      aiPolicyHandlers({ view: "real_firm" }),
      `GET ${path}`,
      request(
        "GET",
        path,
        {},
        undefined,
        "margaret-okonkwo",
        new URLSearchParams({ engagement_type: "tax_return" }),
      ),
    );
    expect(real.body).toMatchObject({
      auto_mode_effective: false,
      auto_mode_lock: "real_firm_season_1",
    });
  });
});
