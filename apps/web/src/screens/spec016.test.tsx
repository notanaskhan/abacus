// SPEC-016: the firm shell, engagement screens, methodology admin and the client portal.
import type { EngagementGraphOut, MeOut, NotificationPageOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NotificationPanel } from "../shell/NotificationPanel";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { takeTokenFromFragment } from "./ClientAccept";
import { Contacts } from "./Contacts";
import { Layout } from "./Layout";
import { MapView } from "./MapView";
import { Methodology } from "./Methodology";
import { Overview } from "./Overview";

const E = "e1";

function graph(over: Partial<EngagementGraphOut> = {}): EngagementGraphOut {
  return {
    engagement: {
      id: E,
      name: "FY2026 audit",
      client_name: "Northwind",
      client_entity_name: "Northwind Ltd",
      fiscal_period_start: "2026-01-01",
      fiscal_period_end: "2026-12-31",
      status: "active",
    },
    team: [{ user_id: "u1", display_name: "Dana Leader", role: "engagement_partner" }],
    methodology: { template_id: "t", template_name: "Audit core", version_id: "v1", version: 1 },
    snapshot_id: "s1",
    areas: [
      {
        code: "AR",
        name: "Receivables",
        accounts: [{ code: "1100", name: "Trade debtors", balance: "125000.00" }],
        items: [
          {
            id: "i1",
            description: "Aged receivables listing",
            status: "received",
            retrievability_tier: "A",
            evidence_version_id: "v9",
            screening_action: "needs_revision",
          },
          {
            id: "i2",
            description: "Credit notes after year end",
            status: "open",
            retrievability_tier: "B",
            evidence_version_id: null,
            screening_action: null,
          },
        ],
      },
      { code: "PY", name: "Payroll", accounts: [], items: [] },
    ],
    unmapped_accounts: [{ code: "6900", name: "Sundry", balance: "-42.10" }],
    gaps: {
      areas_without_requests: ["Payroll"],
      areas_with_accounts_without_requests: [],
      unmapped_accounts: [{ code: "6900", name: "Sundry", balance: "-42.10" }],
      items_without_evidence: ["i2"],
    },
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
  sessionStorage.clear();
});

describe("ac2 notifications", () => {
  it("lists notifications as text and marks one read", async () => {
    const page: NotificationPageOut = {
      unread_count: 1,
      items: [
        {
          id: "n1",
          kind: "review.assigned",
          engagement_id: E,
          subject_type: "evidence_version",
          subject_id: "v9",
          created_at: "2026-10-08T10:00:00Z",
          read: false,
        },
      ],
    };
    const { calls } = mockApi({
      "GET /v1/notifications": () => json(page),
      "POST /v1/notifications/n1/read": () => json(page),
    });
    renderRoutes([
      { path: "/", component: () => <NotificationPanel onClose={() => undefined} /> },
    ]);
    expect(await screen.findByText("Evidence was assigned to you for review.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Mark read: Evidence was assigned/ }));
    await waitFor(() => {
      expect(
        calls.some((c) => c.method === "POST" && c.path === "/v1/notifications/n1/read"),
      ).toBe(true);
    });
  });
});

describe("ac3 engagement overview", () => {
  it("shows areas with progress, the selected area's requests with AI-tagged screening, and gaps", async () => {
    mockApi({ [`GET /v1/engagements/${E}/graph`]: () => json(graph()) });
    renderRoutes([{ path: "/", component: () => <Overview engagementId={E} /> }]);
    expect(await screen.findByRole("heading", { name: "Receivables" })).toBeTruthy();
    expect(screen.getByText("Aged receivables listing")).toBeTruthy();
    expect(screen.getByText("AI")).toBeTruthy();
    expect(screen.getAllByText("Needs revision").length).toBeGreaterThan(0);
    expect(screen.getByText("No requests")).toBeTruthy();
    const gaps = screen.getByRole("region", { name: "Coverage gaps" });
    expect(within(gaps).getByText("Unmapped accounts with balances")).toBeTruthy();
  });
});

describe("ac4 engagement map", () => {
  it("puts gaps first and shows accounts with tabular balances", async () => {
    mockApi({ [`GET /v1/engagements/${E}/graph`]: () => json(graph()) });
    renderRoutes([{ path: "/", component: () => <MapView engagementId={E} /> }]);
    const headings = await screen.findAllByRole("heading", { level: 2 });
    expect(headings[0]?.textContent).toBe("Gaps");
    expect(screen.getByText("Sundry")).toBeTruthy();
    expect(screen.getByText("Trade debtors")).toBeTruthy();
  });
});

describe("ac5 client contacts", () => {
  it("shows a pending invitation with its email and role, never a link, and invites by email", async () => {
    const { calls } = mockApi({
      [`GET /v1/engagements/${E}/client-contacts`]: () =>
        json([
          {
            kind: "invitation",
            id: "inv1",
            role: "client_admin",
            email: "fd@northwind.test",
            expires_at: "2026-10-15T00:00:00Z",
          },
        ]),
      [`POST /v1/engagements/${E}/client-invitations`]: () => json({ invitation_id: "inv2" }, 201),
    });
    renderRoutes([{ path: "/", component: () => <Contacts engagementId={E} /> }]);
    expect(await screen.findByText("fd@northwind.test")).toBeTruthy();
    expect(screen.getByText("Client admin")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/token=|\/client\/accept/);
    fireEvent.click(
      screen.getAllByRole("button", { name: "Invite client contact" })[0] as HTMLElement,
    );
    fireEvent.change(await screen.findByLabelText("Email"), {
      target: { value: "ap@northwind.test" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send invitation" }));
    await waitFor(() => {
      const posted = calls.find((c) => c.method === "POST");
      expect(posted?.body).toEqual({ email: "ap@northwind.test", role: "client_admin" });
    });
  });
});

describe("ac6 methodology upload", () => {
  it("shows each workbook problem by sheet, row and column", async () => {
    mockApi({
      "GET /v1/methodology/templates": () => json([]),
      "POST /v1/methodology/templates/Audit%20core/versions": () =>
        json(
          {
            detail: [
              { loc: ["body", "Requests", 4, "tier"], msg: "invalid_tier", type: "invalid_tier" },
            ],
          },
          422,
        ),
      "POST /v1/methodology/templates/Audit core/versions": () =>
        json(
          {
            detail: [
              { loc: ["body", "Requests", 4, "tier"], msg: "invalid_tier", type: "invalid_tier" },
            ],
          },
          422,
        ),
    });
    renderRoutes([{ path: "/", component: Methodology }]);
    fireEvent.change(await screen.findByLabelText("Template name"), {
      target: { value: "Audit core" },
    });
    const file = new File(['"x"'], "m.xlsx");
    fireEvent.change(screen.getByLabelText("Workbook (.xlsx)"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByText("Requests · row 4 · tier")).toBeTruthy();
    expect(screen.getByText("The tier must be A, B, C, D or E.")).toBeTruthy();
  });

  it("asks the admin to confirm it's them when the action needs recent MFA", async () => {
    mockApi({
      "GET /v1/methodology/templates": () => json([]),
      "POST /v1/methodology/templates/Audit%20core/versions": () =>
        json({ detail: "forbidden" }, 403),
      "POST /v1/methodology/templates/Audit core/versions": () =>
        json({ detail: "forbidden" }, 403),
    });
    renderRoutes([{ path: "/", component: Methodology }]);
    fireEvent.change(await screen.findByLabelText("Template name"), {
      target: { value: "Audit core" },
    });
    fireEvent.change(screen.getByLabelText("Workbook (.xlsx)"), {
      target: { files: [new File(['"x"'], "m.xlsx")] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByRole("dialog", { name: "Confirm it's you" })).toBeTruthy();
  });
});

describe("ac7 accepting an invitation", () => {
  it("moves the token out of the address bar into this tab's storage only", () => {
    const replace = vi.spyOn(window.history, "replaceState");
    window.location.hash = "#token=abcdefghijklmnopqrstuvwxyz0123";
    takeTokenFromFragment();
    expect(sessionStorage.getItem("abacus.invitation")).toBe("abcdefghijklmnopqrstuvwxyz0123");
    expect(localStorage.getItem("abacus.invitation")).toBeNull();
    expect(replace).toHaveBeenCalled();
  });
});

describe("ac8 client users stay in the client portal", () => {
  it("sends a client member from firm routes to /client", async () => {
    const client: MeOut = {
      user_id: "c1",
      display_name: "Fay Director",
      email: "fd@northwind.test",
      active_tenant_id: "t1",
      memberships: [{ tenant_id: "t1", firm_name: "Dev firm", firm_role: null, kind: "client" }],
    };
    mockApi({ "GET /v1/me": () => json(client) });
    // In the app the client tree sits outside the firm layout; here the layout is the firm page.
    renderRoutes([
      { path: "/", component: Layout },
      { path: "/client", component: () => <p>Client home</p> },
    ]);
    expect(await screen.findByText("Client home")).toBeTruthy();
    expect(screen.queryByRole("navigation", { name: "Workspace" })).toBeNull();
  });
});
