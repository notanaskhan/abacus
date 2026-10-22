// SPEC-024 (TASK-041): people, firm roles and invitations; joining from the emailed link.
import type { StaffListOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { FirmPeople } from "./FirmPeople";

const LIST: StaffListOut = {
  members: [
    {
      user_id: "u-me",
      display_name: "Ada Admin",
      email: "ada@firm.test",
      firm_role: "firm_admin",
      status: "active",
    },
    {
      user_id: "u-s",
      display_name: "Sam Staff",
      email: "sam@firm.test",
      firm_role: null,
      status: "active",
    },
    {
      user_id: "u-x",
      display_name: "Rex Gone",
      email: "rex@firm.test",
      firm_role: null,
      status: "revoked",
    },
  ],
  invitations: [
    {
      id: "inv1",
      email: "new@firm.test",
      firm_role: "practice_leader",
      expires_at: "2026-10-23T00:00:00Z",
      created_at: "2026-10-09T00:00:00Z",
    },
  ],
};

const ME = {
  user_id: "u-me",
  display_name: "Ada Admin",
  email: "ada@firm.test",
  active_tenant_id: "t1",
  memberships: [{ tenant_id: "t1", firm_name: "Firm", firm_role: "firm_admin", kind: "staff" }],
};

const page = (): void => {
  renderRoutes([{ path: "/", component: FirmPeople }]);
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

describe("ac3 invitations", () => {
  it("invites someone with a role and lists pending invitations with resend and revoke", async () => {
    const { calls } = mockApi({
      "GET /v1/me": () => json(ME),
      "GET /v1/firm/staff": () => json(LIST),
      "POST /v1/firm/staff/invitations": () => json({ id: "inv2" }, 201),
      "POST /v1/firm/staff/invitations/inv1/resend": () => json({ id: "inv1" }),
    });
    page();
    fireEvent.change(await screen.findByLabelText("Email"), {
      target: { value: "lee@firm.test" },
    });
    fireEvent.change(screen.getByLabelText("Role"), { target: { value: "quality_partner" } });
    fireEvent.click(screen.getByRole("button", { name: "Send invitation" }));
    await waitFor(() => {
      expect(calls.find((c) => c.path === "/v1/firm/staff/invitations")?.body).toEqual({
        email: "lee@firm.test",
        firm_role: "quality_partner",
      });
    });
    expect(screen.getByText(/new@firm.test · Practice leader/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Resend" }));
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/inv1/resend"))).toBe(true);
    });
  });
});

describe("ac4 roles and access", () => {
  it("changes a role, explains the last-admin refusal, and removes access after confirming", async () => {
    const { calls } = mockApi({
      "GET /v1/me": () => json(ME),
      "GET /v1/firm/staff": () => json(LIST),
      "PUT /v1/firm/staff/u-me/role": () => json({ detail: "last_admin" }, 409),
      "PUT /v1/firm/staff/u-s/role": () => json({ id: "u-s" }),
      "POST /v1/firm/staff/u-s/revoke": () => json({ id: "u-s" }),
    });
    page();
    fireEvent.change(await screen.findByLabelText("Role for Sam Staff"), {
      target: { value: "practice_leader" },
    });
    await waitFor(() => {
      expect(calls.find((c) => c.path === "/v1/firm/staff/u-s/role")?.body).toEqual({
        firm_role: "practice_leader",
      });
    });
    fireEvent.change(screen.getByLabelText("Role for Ada Admin"), { target: { value: "" } });
    expect(
      await screen.findByText("The firm needs at least one firm administrator."),
    ).toBeTruthy();
    // Nobody removes their own access here; a revoked person shows as such.
    const rows = screen.getAllByRole("row");
    expect(
      within(rows[1] as HTMLElement).queryByRole("button", { name: "Remove access" }),
    ).toBeNull();
    expect(screen.getByText("Access removed")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Remove access" }));
    const dialog = await screen.findByRole("dialog", { name: "Remove Sam Staff's access?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Remove access" }));
    await waitFor(() => {
      expect(calls.some((c) => c.path === "/v1/firm/staff/u-s/revoke")).toBe(true);
    });
  });

  it("asks for a recent sign-in when the list is refused", async () => {
    mockApi({
      "GET /v1/me": () => json(ME),
      "GET /v1/firm/staff": () => json({ detail: "forbidden" }, 403),
    });
    page();
    expect(await screen.findByRole("dialog", { name: "Confirm it's you" })).toBeTruthy();
  });
});
