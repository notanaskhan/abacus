// SPEC-304 (TASK-305): the audit log explorer filters, pages back and narrows to a target.
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { actionLabel, AuditLog, toQuery } from "./AuditLog";

function event(seq: number, over = {}) {
  return {
    seq,
    occurred_at: "2026-10-20T10:00:00Z",
    actor_kind: "human",
    actor_id: "u1",
    actor_name: "Dana Leader",
    action: "finding.severity_concluded",
    target_type: "finding",
    target_id: "aaaaaaaa-0000-0000-0000-000000000001",
    before_ref: null,
    after_ref: { severity: 1 },
    trace_id: null,
    ...over,
  };
}

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("SPEC-304 audit log", () => {
  it("labels actions and builds the query (ac2)", () => {
    expect(actionLabel("finding.severity_concluded")).toBe("Finding · severity concluded");
    expect(
      toQuery({
        action: "",
        actorKind: "agent",
        targetType: "",
        targetId: " x ",
        from: "2026-10-01",
        to: "2026-10-20",
      }),
    ).toEqual({
      actor_kind: "agent",
      target_id: "x",
      since: "2026-10-01T00:00:00Z",
      until: "2026-10-21T00:00:00.000Z",
    });
  });

  it("shows events, loads older ones, and narrows to a target (ac1, ac2)", async () => {
    const { calls } = mockApi({
      "GET /v1/firm/audit-events/facets": () =>
        json({ actions: ["finding.severity_concluded"], target_types: ["finding"] }),
      "GET /v1/firm/audit-events": () => {
        const n = calls.filter((x) => x.path === "/v1/firm/audit-events").length;
        return n === 1
          ? json({ events: [event(9)], next_before: 9 })
          : json({
              events: [
                event(8, { actor_kind: "agent", actor_id: "engagement.agent", actor_name: null }),
              ],
              next_before: null,
            });
      },
    });
    renderRoutes([{ path: "/", component: AuditLog }]);
    expect(await screen.findByText("Dana Leader")).toBeTruthy();
    expect(screen.getByRole("cell", { name: "Finding · severity concluded" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Load older" }));
    expect(await screen.findByText("engagement.agent")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Load older" })).toBeNull();
    fireEvent.click(screen.getAllByTitle("Show this target's history")[0] as HTMLElement);
    await waitFor(() => {
      expect(screen.getByLabelText<HTMLInputElement>("Target ID").value).toBe(
        "aaaaaaaa-0000-0000-0000-000000000001",
      );
    });
  });

  it("explains when the person may not read it (ac4)", async () => {
    mockApi({
      "GET /v1/firm/audit-events/facets": () => json({ detail: "forbidden" }, 403),
      "GET /v1/firm/audit-events": () => json({ detail: "forbidden" }, 403),
    });
    renderRoutes([{ path: "/", component: AuditLog }]);
    expect(await screen.findByText("The audit log isn't available")).toBeTruthy();
  });
});
