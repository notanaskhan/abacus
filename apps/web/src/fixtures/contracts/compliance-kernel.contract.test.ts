// Q-02-T38: compliance-kernel v1.1 consumer fixtures for G-02's ADM-06 (docs/contracts/
// compliance-kernel.md). Typed with the generated client, so a breaking change fails `tsc`, and
// checked against the OpenAPI document at run time. The pytest half is
// backend/tests/contracts/compliance_kernel/.
import { describe, expect, it } from "vitest";
import type { FixtureRequest } from "../../app-core/fixture-mode";
import { complianceHandlers } from "../handlers/compliance";
import { validateResponse } from "../schema-check";
import { EXPORT_HISTORY, INC_2026_005, firmExportPage } from "../seed/compliance";

const GB = 1000 ** 3;

describe("compliance-kernel v1.1 fixtures", () => {
  it("INC-2026-005 reads Day 4 of 30 with notice due Oct 10 and is not yet an event", () => {
    expect(INC_2026_005.clock_day).toBe(4);
    expect(INC_2026_005.clock_days).toBe(30);
    expect(INC_2026_005.ftc_notify_by).toBe("2026-10-10");
    expect(INC_2026_005.notification_event).toBe(false);
    expect(INC_2026_005.consumers_affected).toBe(0);
  });

  it("the history reads Sep 1 386 GB, Aug 1 371 GB and Jul 1 359 GB", () => {
    expect(EXPORT_HISTORY.map((e) => [e.requested_at.slice(0, 10), e.size_bytes])).toEqual([
      ["2026-09-01", 386 * GB],
      ["2026-08-01", 371 * GB],
      ["2026-07-01", 359 * GB],
    ]);
  });

  it("ADM-06 g: Felix Andersen's request waits for Margaret Okonkwo", () => {
    const [first] = firmExportPage(true).items;
    expect(first?.status).toBe("awaiting_approval");
    expect(first?.requested_by.display_name).toBe("Felix Andersen");
    expect(first?.approver.display_name).toBe("Margaret Okonkwo");
  });

  it("the list matches the OpenAPI document with and without the request", () => {
    for (const requested of [false, true]) {
      expect(validateResponse("GET", "/v1/firm/data-exports", firmExportPage(requested))).toEqual(
        [],
      );
    }
  });

  it("the requester can't approve; the named approver can, once", async () => {
    const requester = complianceHandlers({ requested: true });
    const id = firmExportPage(true).items[0]?.id ?? "";
    const request: FixtureRequest = {
      method: "POST",
      path: `/v1/firm/data-exports/${id}/approve`,
      params: { export_id: id },
      query: new URLSearchParams(),
      body: undefined,
      persona: undefined,
    };
    const refused = await requester["POST /v1/firm/data-exports/{export_id}/approve"]?.(request);
    expect(refused?.status).toBe(409);
    const approver = complianceHandlers({ requested: true, approver: true });
    const approved = await approver["POST /v1/firm/data-exports/{export_id}/approve"]?.(request);
    expect(approved?.status).toBe(200);
    const again = await approver["POST /v1/firm/data-exports/{export_id}/approve"]?.(request);
    expect(again?.status).toBe(409);
  });
});
