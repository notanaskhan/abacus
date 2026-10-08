// SPEC-019: knowledge, budget and spend, support access and walls.
import type { KnowledgeDocumentOut, MeOut, SupportSessionOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { AdminLayout } from "./AdminLayout";
import { Budget } from "./Budget";
import { Knowledge } from "./Knowledge";
import { KnowledgeDocuments } from "./KnowledgeDocuments";
import { SupportAccess } from "./SupportAccess";
import { Walls } from "./Walls";

function me(role: "firm_admin" | "practice_leader" | null): MeOut {
  return {
    user_id: "u-a",
    display_name: "Ada Admin",
    email: "a@dev.test",
    active_tenant_id: "t1",
    memberships: [{ tenant_id: "t1", firm_name: "Dev firm", firm_role: role, kind: "staff" }],
  };
}

function doc(over: Partial<KnowledgeDocumentOut> = {}): KnowledgeDocumentOut {
  return {
    id: "d1",
    title: "Cash procedures",
    status: "ready",
    chunk_count: 4,
    created_at: "2026-10-01T00:00:00Z",
    failure_code: null,
    media_type: "text/plain",
    source_kind: "firm_own",
    ...over,
  };
}

function session(over: Partial<SupportSessionOut> = {}): SupportSessionOut {
  return {
    id: "s1",
    staff_id: "st1",
    staff_subject: "support@abacus",
    reason: "Customer reported a stuck import on the requests board",
    scope: "metadata",
    status: "requested",
    emergency: false,
    acknowledged: false,
    approved_by_kind: null,
    duration_minutes: 60,
    requests: 0,
    created_at: "2026-10-08T09:00:00Z",
    starts_at: null,
    ended_at: null,
    expires_at: null,
    ...over,
  };
}

const forbidden = (): Response => json({ detail: "forbidden" }, 403);

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("ac1 knowledge search", () => {
  it("shows title, section, passage and score for each result", async () => {
    const { calls } = mockApi({
      "POST /v1/knowledge/search": () =>
        json([
          {
            document_id: "d1",
            title: "Cash procedures",
            heading_path: "Cash > Cut-off",
            position: 2,
            text: "Test receipts either side of year end.",
            score: 0.87,
          },
        ]),
    });
    renderRoutes([{ path: "/", component: Knowledge }]);
    fireEvent.change(await screen.findByLabelText("What are you looking for?"), {
      target: { value: "cash cut-off" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText("Cash procedures")).toBeTruthy();
    expect(screen.getByText("Cash > Cut-off")).toBeTruthy();
    expect(screen.getByText("Test receipts either side of year end.")).toBeTruthy();
    expect(screen.getByText("Match 0.87")).toBeTruthy();
    expect(calls.find((c) => c.path === "/v1/knowledge/search")?.body).toEqual({
      query: "cash cut-off",
      k: 10,
    });
  });

  it("shows a helpful empty state when nothing matches, and can't search an empty query", async () => {
    mockApi({ "POST /v1/knowledge/search": () => json([]) });
    renderRoutes([{ path: "/", component: Knowledge }]);
    const button = await screen.findByRole("button", { name: "Search" });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("What are you looking for?"), {
      target: { value: "leases" },
    });
    fireEvent.click(button);
    expect(await screen.findByText("Nothing found")).toBeTruthy();
  });
});

describe("ac2 knowledge documents", () => {
  it("adds a document that shows as processing, then ready without a reload", async () => {
    let listed = 0;
    let added = false;
    const { calls } = mockApi({
      "GET /v1/knowledge/documents": () => {
        if (!added) return json([]);
        listed += 1;
        return json([doc({ status: listed > 1 ? "ready" : "pending", chunk_count: 0 })]);
      },
      "POST /v1/knowledge/documents": () => {
        added = true;
        return json(doc({ status: "pending" }), 202);
      },
    });
    renderRoutes([{ path: "/", component: KnowledgeDocuments }]);
    expect(await screen.findByText("No documents yet")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Cash procedures" } });
    fireEvent.change(screen.getByLabelText("Text"), { target: { value: "# Cash\nCount it." } });
    fireEvent.click(screen.getByRole("button", { name: "Add document" }));
    expect(await screen.findByText("Processing")).toBeTruthy();
    expect(await screen.findByText("Ready", {}, { timeout: 5000 })).toBeTruthy();
    expect(calls.find((c) => c.method === "POST")?.body).toMatchObject({
      title: "Cash procedures",
      source_kind: "firm_own",
      media_type: "text/plain",
    });
  }, 10000);

  it("asks before withdrawing, and explains a failed document in plain words", async () => {
    const { calls } = mockApi({
      "GET /v1/knowledge/documents": () =>
        json([
          doc(),
          doc({ id: "d2", title: "Leases", status: "failed", failure_code: "embed_refused" }),
        ]),
      "POST /v1/knowledge/documents/d1/withdraw": () => json(doc({ status: "withdrawn" })),
    });
    renderRoutes([{ path: "/", component: KnowledgeDocuments }]);
    expect(await screen.findByText(/couldn't be processed/)).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: "Withdraw" })[0] as HTMLElement);
    const dialog = await screen.findByRole("dialog", { name: 'Withdraw "Cash procedures"?' });
    fireEvent.click(within(dialog).getByRole("button", { name: "Withdraw" }));
    await waitFor(() => {
      expect(calls.some((c) => c.path === "/v1/knowledge/documents/d1/withdraw")).toBe(true);
    });
  });
});

const BUDGET = {
  spent_this_month_usd: "420.00",
  monthly_soft_usd: "400.00",
  monthly_hard_usd: "500.00",
  plan_cap_usd: "1000.00",
  is_default: false,
};

describe("ac3 budget", () => {
  it("shows spend against both limits as numbers and a meter, and asks a firm admin to confirm it's them", async () => {
    mockApi({
      "GET /v1/me": () => json(me("firm_admin")),
      "GET /v1/budget": () => json(BUDGET),
      "PUT /v1/budget": forbidden,
      "GET /v1/metering": () => json([]),
      "GET /v1/engagements": () => json([]),
    });
    renderRoutes([{ path: "/", component: Budget }]);
    expect(await screen.findByText("$420.00")).toBeTruthy();
    expect(screen.getByText(/Soft limit passed/)).toBeTruthy();
    const meter = screen.getByRole("meter", { name: "Spend against the hard limit" });
    expect(meter.getAttribute("aria-valuenow")).toBe("420");
    expect(screen.getByText(/Plan limit \$1,000.00/)).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: "Set budget" }));
    fireEvent.change(screen.getByLabelText("Hard limit (USD)"), { target: { value: "600" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("dialog", { name: "Confirm it's you" })).toBeTruthy();
  });

  it("is read-only for a practice leader", async () => {
    mockApi({
      "GET /v1/me": () => json(me("practice_leader")),
      "GET /v1/budget": () => json(BUDGET),
      "GET /v1/metering": () => json([]),
      "GET /v1/engagements": () => json([]),
    });
    renderRoutes([{ path: "/", component: Budget }]);
    expect(await screen.findByText("$420.00")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Set budget" })).toBeNull();
  });
});

describe("ac4 metering", () => {
  it("shows engagement names or short IDs, sorts, totals, and switches to today", async () => {
    const { calls } = mockApi({
      "GET /v1/me": () => json(me("firm_admin")),
      "GET /v1/budget": () => json(BUDGET),
      "GET /v1/metering": () =>
        json([
          { engagement_id: "e-known", agent_id: "engagement_agent", cost_usd: "10.50" },
          { engagement_id: "abcdef1234567890", agent_id: "screening", cost_usd: "30.00" },
        ]),
      "GET /v1/engagements": () =>
        json([{ id: "e-known", name: "FY2026 audit", client_name: "Northwind" }]),
    });
    renderRoutes([{ path: "/", component: Budget }]);
    expect(await screen.findByText("Northwind · FY2026 audit")).toBeTruthy();
    expect(screen.getByText("Engagement abcdef12")).toBeTruthy();
    expect(screen.getByText("$40.50")).toBeTruthy();
    const firstRow = (): string => screen.getAllByRole("row")[1]?.textContent ?? "";
    expect(firstRow()).toContain("Engagement abcdef12");
    fireEvent.click(screen.getByRole("button", { name: "Engagement" }));
    expect(firstRow()).toContain("Engagement abcdef12");
    fireEvent.click(screen.getByRole("button", { name: "Agent" }));
    expect(firstRow()).toContain("engagement_agent");
    fireEvent.click(screen.getByRole("button", { name: "Today" }));
    await waitFor(() => {
      expect(calls.some((c) => c.path === "/v1/metering" && c.method === "GET")).toBe(true);
    });
  });
});

describe("ac5 support access", () => {
  it("shows each session's details and approves after confirmation, asking for a fresh sign-in", async () => {
    mockApi({
      "GET /v1/support-sessions": () => json([session()]),
      "POST /v1/support-sessions/s1/approve": forbidden,
    });
    renderRoutes([{ path: "/", component: SupportAccess }]);
    expect(await screen.findByText("support@abacus")).toBeTruthy();
    expect(screen.getByText(/stuck import/)).toBeTruthy();
    expect(screen.getByText("Metadata only")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    const dialog = await screen.findByRole("dialog", { name: "Approve support session" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Approve" }));
    expect(await screen.findByRole("dialog", { name: "Confirm it's you" })).toBeTruthy();
  });

  it("says a session was already handled when someone else got there first", async () => {
    mockApi({
      "GET /v1/support-sessions": () => json([session({ status: "active" })]),
      "POST /v1/support-sessions/s1/revoke": () =>
        json({ detail: "support_session_conflict" }, 409),
    });
    renderRoutes([{ path: "/", component: SupportAccess }]);
    fireEvent.click(await screen.findByRole("button", { name: "Revoke" }));
    const dialog = await screen.findByRole("dialog", { name: "Revoke support session" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Revoke" }));
    expect(await screen.findByText("Already handled. The list has been refreshed.")).toBeTruthy();
  });

  it("shows an emergency banner on admin pages until acknowledged", async () => {
    mockApi({
      "GET /v1/me": () => json(me("firm_admin")),
      "GET /v1/support-sessions": () =>
        json([session({ status: "active", emergency: true, approved_by_kind: "emergency" })]),
    });
    renderRoutes([{ path: "/", component: AdminLayout }]);
    expect(await screen.findByText("Emergency support access needs your review")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Walls" })).toBeTruthy();
  });

  it("shows practice leaders only the tabs they may use, without the banner", async () => {
    const { calls } = mockApi({ "GET /v1/me": () => json(me("practice_leader")) });
    renderRoutes([{ path: "/", component: AdminLayout }]);
    expect(await screen.findByRole("link", { name: "Budget" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Walls" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Support access" })).toBeNull();
    expect(calls.some((c) => c.path === "/v1/support-sessions")).toBe(false);
  });
});

describe("ac6 walls", () => {
  it("asks for a fresh sign-in before showing walls", async () => {
    mockApi({ "GET /v1/walls": forbidden });
    renderRoutes([{ path: "/", component: Walls }]);
    expect(await screen.findByRole("dialog", { name: "Confirm it's you" })).toBeTruthy();
  });

  it("creates a wall from the pickers, removes one with confirmation, and explains refusals", async () => {
    const { calls } = mockApi({
      "GET /v1/walls": () =>
        json([
          {
            id: "w1",
            user_id: "u-s",
            client_id: "c1",
            status: "active",
            created_at: "2026-10-01T00:00:00Z",
            created_by: "u-a",
            removed_at: null,
            removed_by: null,
          },
        ]),
      "GET /v1/firm/members": () =>
        json([
          { user_id: "u-s", display_name: "Sam Staff" },
          { user_id: "u-a", display_name: "Ada Admin" },
        ]),
      "GET /v1/firm/clients": () => json([{ client_id: "c1", name: "Northwind" }]),
      "POST /v1/walls": () => json({ detail: "wall_exists" }, 409),
      "POST /v1/walls/w1/remove": () => json({ detail: "own_wall" }, 409),
    });
    renderRoutes([{ path: "/", component: Walls }]);
    expect(await screen.findByRole("cell", { name: "Sam Staff" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Person"), { target: { value: "u-s" } });
    fireEvent.change(screen.getByLabelText("Client"), { target: { value: "c1" } });
    fireEvent.click(screen.getByRole("button", { name: "Add wall" }));
    expect(
      await screen.findByText("That person is already walled off from this client."),
    ).toBeTruthy();
    expect(calls.find((c) => c.path === "/v1/walls" && c.method === "POST")?.body).toEqual({
      user_id: "u-s",
      client_id: "c1",
    });
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    const dialog = await screen.findByRole("dialog", { name: "Remove wall" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Remove" }));
    expect(await screen.findByText(/can't lift a wall on yourself/)).toBeTruthy();
  });
});

describe("ac7 loading and error states", () => {
  it("shows an error state when a list fails to load", async () => {
    mockApi({ "GET /v1/support-sessions": () => json({ detail: "unavailable" }, 503) });
    renderRoutes([{ path: "/", component: SupportAccess }]);
    expect(await screen.findByText("Couldn't load support sessions")).toBeTruthy();
  });

  it("shows an empty state with no walls", async () => {
    mockApi({
      "GET /v1/walls": () => json([]),
      "GET /v1/firm/members": () => json([]),
      "GET /v1/firm/clients": () => json([]),
    });
    renderRoutes([{ path: "/", component: Walls }]);
    expect(await screen.findByText(/No walls/)).toBeTruthy();
  });
});
