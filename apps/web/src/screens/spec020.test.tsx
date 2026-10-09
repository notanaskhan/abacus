// SPEC-020 (TASK-035): the client portal's engagement page, client uploads, and the Board switch.
import type { EngagementOut, RequestItemOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { ClientEngagement } from "./ClientEngagement";

const E = "e1";
const ENGAGEMENT: EngagementOut = {
  id: E,
  name: "FY2026 audit",
  client_name: "Northwind",
  client_entity_name: "Northwind Ltd",
  fiscal_period_start: "2026-01-01",
  fiscal_period_end: "2026-12-31",
  status: "active",
  team: [],
} as unknown as EngagementOut;

function item(over: Partial<RequestItemOut> = {}): RequestItemOut {
  return {
    id: "i1",
    engagement_id: E,
    description: "Bank statements for December",
    audit_area: "Cash",
    status: "open",
    created_at: "2026-10-01T00:00:00Z",
    evidence_version_id: null,
    retrievability_tier: null,
    client_visible: true,
    client_assignee_user_id: null,
    ...over,
  };
}

const page = (): void => {
  renderRoutes([{ path: "/", component: () => <ClientEngagement engagementId={E} /> }]);
};

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("ac1 client engagement page", () => {
  it("shows the engagement and its requests grouped by area", async () => {
    mockApi({
      [`GET /v1/engagements/${E}`]: () => json(ENGAGEMENT),
      [`GET /v1/engagements/${E}/request-items`]: () =>
        json([item(), item({ id: "i2", description: "Payroll summary", audit_area: "Payroll" })]),
      [`GET /v1/engagements/${E}/client-contacts`]: () => json({ detail: "forbidden" }, 403),
    });
    page();
    expect(await screen.findByRole("heading", { name: "FY2026 audit" })).toBeTruthy();
    expect(await screen.findByRole("region", { name: "Cash" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Payroll" })).toBeTruthy();
    expect(screen.getByText("Bank statements for December")).toBeTruthy();
    // A contributor (contacts refused) gets no assignee picker.
    expect(screen.queryByLabelText("Assigned to")).toBeNull();
  });

  it("tells a contributor with nothing assigned what happens next", async () => {
    mockApi({
      [`GET /v1/engagements/${E}`]: () => json(ENGAGEMENT),
      [`GET /v1/engagements/${E}/request-items`]: () => json([]),
      [`GET /v1/engagements/${E}/client-contacts`]: () => json({ detail: "forbidden" }, 403),
    });
    page();
    expect(await screen.findByText(/Nothing is assigned to you yet/)).toBeTruthy();
  });

  it("lets a client admin assign a request to a contributor", async () => {
    const { calls } = mockApi({
      [`GET /v1/engagements/${E}`]: () => json(ENGAGEMENT),
      [`GET /v1/engagements/${E}/request-items`]: () => json([item()]),
      [`GET /v1/engagements/${E}/client-contacts`]: () =>
        json([
          {
            kind: "member",
            id: "u-c",
            role: "client_contributor",
            email: null,
            expires_at: null,
            display_name: "Cara Contributor",
          },
        ]),
      [`PUT /v1/engagements/${E}/request-items/i1/client-assignee`]: () =>
        json(item({ client_assignee_user_id: "u-c" })),
    });
    page();
    const picker = await screen.findByLabelText("Assigned to");
    fireEvent.change(picker, { target: { value: "u-c" } });
    await waitFor(() => {
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ user_id: "u-c" });
    });
  });
});

describe("ac8 ac9 uploads", () => {
  it("uploads each chosen file, shows its result, and explains a refusal in plain words", async () => {
    const { calls } = mockApi({
      [`GET /v1/engagements/${E}`]: () => json(ENGAGEMENT),
      [`GET /v1/engagements/${E}/request-items`]: () => json([item()]),
      [`GET /v1/engagements/${E}/client-contacts`]: () => json({ detail: "forbidden" }, 403),
      [`POST /v1/engagements/${E}/request-items/i1/uploads`]: (call) =>
        calls.filter((c) => c.method === "POST").length === 1
          ? json(
              {
                evidence_version_id: "v1",
                file_name: "statement.pdf",
                media_type: "application/pdf",
                size_bytes: 3,
                uploaded_by: "u-c",
                uploaded_by_name: "Cara",
                uploaded_at: "2026-10-09T10:00:00Z",
              },
              201,
            )
          : json({ detail: call.method === "POST" ? "upload_type_not_allowed" : "" }, 422),
      [`GET /v1/engagements/${E}/request-items/i1/uploads`]: () =>
        json([
          {
            evidence_version_id: "v1",
            file_name: "statement.pdf",
            media_type: "application/pdf",
            size_bytes: 3,
            uploaded_by: "u-c",
            uploaded_by_name: "Cara",
            uploaded_at: "2026-10-09T10:00:00Z",
          },
        ]),
    });
    page();
    const input = await screen.findByLabelText("Upload files for Bank statements for December");
    fireEvent.change(input, {
      target: {
        files: [new File(['"x"'], "statement.pdf"), new File(['"y"'], "tool.exe")],
      },
    });
    const progress = await screen.findByRole("list", { name: "Files being uploaded" });
    expect(await within(progress).findByText("Uploaded")).toBeTruthy();
    expect(
      await within(progress).findByText(
        "Only PDF, Excel, Word, CSV, PNG and JPEG files can be uploaded.",
      ),
    ).toBeTruthy();
    const posts = calls.filter((c) => c.method === "POST");
    expect(posts).toHaveLength(2);
    const history = await screen.findByRole("list", { name: "Uploaded files" });
    expect(within(history).getByText("statement.pdf")).toBeTruthy();
  });

  it("offers no upload on a request that no longer takes files", async () => {
    mockApi({
      [`GET /v1/engagements/${E}`]: () => json(ENGAGEMENT),
      [`GET /v1/engagements/${E}/request-items`]: () =>
        json([item({ status: "ready_for_review" })]),
      [`GET /v1/engagements/${E}/client-contacts`]: () => json({ detail: "forbidden" }, 403),
    });
    page();
    expect(await screen.findByText("Bank statements for December")).toBeTruthy();
    expect(screen.queryByLabelText(/Upload files for/)).toBeNull();
  });
});

describe("ac7 states", () => {
  it("shows an error when the requests can't load", async () => {
    mockApi({
      [`GET /v1/engagements/${E}`]: () => json(ENGAGEMENT),
      [`GET /v1/engagements/${E}/request-items`]: () => json({ detail: "unavailable" }, 503),
      [`GET /v1/engagements/${E}/client-contacts`]: () => json([]),
    });
    page();
    expect(await screen.findByText("Couldn't load your requests")).toBeTruthy();
  });
});
