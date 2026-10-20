// SPEC-042 (TASK-106): the client's words, "This doesn't apply" with a reason (and Undo), and
// "Mark as done" once everything is done.
import type { EngagementOut, RequestItemOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { ClientEngagement } from "./ClientEngagement";

const E = "e1";
const ITEMS = `/v1/engagements/${E}/request-items`;
const ENGAGEMENT = {
  id: E,
  name: "FY2026 audit",
  client_name: "Northwind",
  fiscal_period_start: "2026-01-01",
  fiscal_period_end: "2026-12-31",
} as unknown as EngagementOut;

function item(over: Partial<RequestItemOut> = {}): RequestItemOut {
  return {
    id: "i1",
    engagement_id: E,
    description: "Bank statements for December",
    audit_area: "Cash",
    status: "requested",
    created_at: "2026-10-01T00:00:00Z",
    ...over,
  };
}

function page(items: RequestItemOut[], extra = {}, admin = false) {
  const api = mockApi({
    [`GET /v1/engagements/${E}`]: () => json(ENGAGEMENT),
    [`GET ${ITEMS}`]: () => json(items),
    [`GET /v1/engagements/${E}/client-contacts`]: () =>
      admin ? json([]) : json({ detail: "forbidden" }, 403),
    [`GET ${ITEMS}/i1/client-view`]: () => json({ provided: null, gap: null, history: [] }),
    [`GET ${ITEMS}/client-responses`]: () => json([]),
    [`GET ${ITEMS}/client-done`]: () => json(null),
    ...extra,
  });
  renderRoutes([{ path: "/", component: () => <ClientEngagement engagementId={E} /> }]);
  return api;
}

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("SPEC-042 the portal", () => {
  it("uses the client's words", async () => {
    page([item()]);
    expect(await screen.findByText("To do")).toBeTruthy();
    expect(screen.getByText("0 of 1 done")).toBeTruthy();
  });

  it("says a request doesn't apply, with a reason (ac1)", async () => {
    const { calls } = page([item()], {
      [`POST ${ITEMS}/i1/client-response`]: () => json({ request_item_id: "i1" }, 201),
    });
    fireEvent.click(await screen.findByRole("button", { name: "This doesn't apply…" }));
    fireEvent.click(screen.getByLabelText("I don't have this"));
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/client-response"))?.body).toEqual({
        reason: "dont_have",
      });
    });
  });

  it("shows what they said, with Undo (ac2)", async () => {
    page([item()], {
      [`GET ${ITEMS}/client-responses`]: () =>
        json([
          {
            request_item_id: "i1",
            reason: "sent_another_way",
            note: null,
            by: "u-c",
            name: "Casey",
            at: "2026-10-20T10:00:00Z",
          },
        ]),
    });
    expect(await screen.findByText("You said: Already sent another way")).toBeTruthy();
    expect(screen.getByText("Doesn't apply")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Undo" })).toBeTruthy();
    expect(await screen.findByText("1 of 1 done")).toBeTruthy();
  });

  it("lets the admin mark the list done once everything is done (ac4)", async () => {
    const { calls } = page(
      [item({ status: "uploaded" })],
      {
        [`POST ${ITEMS}/client-done`]: () =>
          json({ by: "u-c", name: "Casey", at: "2026-10-20T10:00:00Z" }, 201),
      },
      true,
    );
    const mark = await screen.findByRole("button", { name: "Mark as done" });
    expect(mark.hasAttribute("disabled")).toBe(false);
    fireEvent.click(mark);
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/client-done"))).toBe(true);
    });
  });
});
