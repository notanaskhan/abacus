// I-01-T13 (I-01 AC2.4, DEC-803): with `home.approvals` off, every Waiting-on-you row opens its
// host gate; a route the manifest cannot build, or a value that is not an opaque id, opens nothing.
import type { HumanGateOut } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { hostHref, routeOf } from "./hosts";

const A = "11111111-1111-4111-8111-111111111111";
const B = "22222222-2222-4222-8222-222222222222";
const C = "33333333-3333-4333-8333-333333333333";

function gate(over: Partial<HumanGateOut>): HumanGateOut {
  return {
    id: A,
    kind: "decision",
    subkind: "acceptance_decision_due",
    band: "decisions",
    state: "open",
    subject: { type: "engagement_acceptance", id: A },
    engagement_id: B,
    client_id: C,
    assignee_user_id: null,
    office_id: null,
    role: null,
    due_on: null,
    blocked: false,
    blocked_reason_code: null,
    created_at: "2026-09-14T14:24:00Z",
    ...over,
  };
}

describe("I-01-T13 row targets", () => {
  it("opens acceptance on CLI-07", () => {
    expect(hostHref(gate({}))).toBe(`/clients/${C}/acceptance/${B}`);
  });

  it.each(["independence_conclusion_due", "independence_confirmation_due", "eqr_eligibility_due"])(
    "opens %s on CLI-08",
    (subkind) => {
      expect(hostHref(gate({ subkind }))).toBe(`/clients/${C}/independence/${B}`);
    },
  );

  it("opens an upload on an assurance PBC list on AUD-03 with the item", () => {
    const row = gate({
      kind: "evidence_review",
      subkind: "evidence_version",
      band: "approvals_sends",
      subject_route: `AUD-03?auditId=${A}&item=${B}`,
    });
    expect(hostHref(row)).toBe(`/audits/${A}/source-documents?item=${B}`);
  });

  it("opens an upload on a binder on BND-02 with the request", () => {
    expect(routeOf(`BND-02?binderId=${A}&request=${B}`)).toBe(`/binders/${A}?request=${B}`);
  });

  it("opens nothing for a screen the manifest does not route or a value that is not an id", () => {
    expect(routeOf(`HOME-02?gate=${A}`)).toBeUndefined();
    expect(routeOf("AUD-03?auditId=Ashford")).toBeUndefined();
    expect(routeOf(`AUD-03?auditId=${A}&item=Ashford`)).toBe(`/audits/${A}/source-documents`);
  });

  it("leaves agent outputs and sends as plain text until their host is built", () => {
    expect(hostHref(gate({ kind: "proposal", subkind: "screening_result" }))).toBeUndefined();
    expect(
      hostHref(gate({ client_id: null, subkind: "acceptance_decision_due" })),
    ).toBeUndefined();
  });
});
