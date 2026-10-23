// ac-test-author: ayushkbhatia
// SPEC-017 AC-7 (TASK-032; back-filled by Q-03-T007): the People tab shows partners and managers
// the actions they may take, shows everyone else the team read-only, and every change asks for
// confirmation before anything is sent.
import type { MeOut, TeamMemberOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { People } from "./People";

const E = "e1";
const TEAM: TeamMemberOut[] = [
  { user_id: "u-p", display_name: "Pat Partner", role: "engagement_partner" },
  { user_id: "u-m", display_name: "Max Manager", role: "manager" },
  { user_id: "u-s", display_name: "Sam Senior", role: "senior" },
];

function me(userId: string, name: string): MeOut {
  return {
    user_id: userId,
    display_name: name,
    email: `${userId}@dev.test`,
    active_tenant_id: "t1",
    server_now: "2026-09-14T14:24:00Z",
    clock_mode: "real",
    memberships: [{ tenant_id: "t1", firm_name: "Dev firm", firm_role: null, kind: "staff" }],
  };
}

function api(viewer: MeOut): ReturnType<typeof mockApi> {
  return mockApi({
    "GET /v1/me": () => json(viewer),
    [`GET /v1/engagements/${E}/team`]: () => json(TEAM),
    [`GET /v1/engagements/${E}/team/candidates`]: () =>
      json([{ user_id: "u-n", display_name: "Nia New" }]),
    [`POST /v1/engagements/${E}/team`]: () => json(TEAM, 201),
    [`PUT /v1/engagements/${E}/team/u-s`]: () => json(TEAM),
    [`DELETE /v1/engagements/${E}/team/u-s`]: () => json(TEAM),
    [`GET /v1/engagements/${E}/client-contacts`]: () => json([]),
  });
}

function sent(calls: { method: string; path: string }[], method: string): number {
  return calls.filter((c) => c.method === method && c.path.includes("/team")).length;
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

describe("SPEC-017 ac7 the People tab", () => {
  it("ac7 shows a partner Add person, every role and Remove on every other member", async () => {
    api(me("u-p", "Pat Partner"));
    renderRoutes([{ path: "/", component: () => <People engagementId={E} /> }]);
    expect(await screen.findByRole("button", { name: "Add person" })).toBeTruthy();
    const role = await screen.findByLabelText<HTMLSelectElement>("Role for Sam Senior");
    expect(Array.from(role.options).map((o) => o.value)).toEqual([
      "engagement_partner",
      "manager",
      "senior",
      "staff",
      "reviewer",
    ]);
    expect(screen.getByLabelText("Role for Max Manager")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Remove" }).length).toBeGreaterThanOrEqual(2);
  });

  it("ac7 shows a manager only the junior roles it may handle", async () => {
    api(me("u-m", "Max Manager"));
    renderRoutes([{ path: "/", component: () => <People engagementId={E} /> }]);
    expect(await screen.findByRole("button", { name: "Add person" })).toBeTruthy();
    expect(screen.queryByLabelText("Role for Pat Partner")).toBeNull();
    const role = await screen.findByLabelText<HTMLSelectElement>("Role for Sam Senior");
    expect(Array.from(role.options).map((o) => o.value)).toEqual(["senior", "staff", "reviewer"]);
  });

  it("ac7 shows anyone else the team read-only", async () => {
    api(me("u-s", "Sam Senior"));
    renderRoutes([{ path: "/", component: () => <People engagementId={E} /> }]);
    expect(await screen.findByText("Pat Partner")).toBeTruthy();
    expect(screen.getByText("Max Manager")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Add person" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Remove" })).toBeNull();
    expect(screen.queryByLabelText("Role for Sam Senior")).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
  });

  it("ac7 asks before removing, and Cancel sends nothing", async () => {
    const { calls } = api(me("u-p", "Pat Partner"));
    renderRoutes([{ path: "/", component: () => <People engagementId={E} /> }]);
    await screen.findByLabelText("Role for Sam Senior");
    const removes = screen.getAllByRole("button", { name: "Remove" });
    fireEvent.click(removes[removes.length - 1] as HTMLElement);
    expect(await screen.findByRole("dialog", { name: "Remove Sam Senior?" })).toBeTruthy();
    expect(sent(calls, "DELETE")).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    expect(sent(calls, "DELETE")).toBe(0);
  });

  it("ac7 asks before changing a role, and only the confirmation sends it", async () => {
    const { calls } = api(me("u-p", "Pat Partner"));
    renderRoutes([{ path: "/", component: () => <People engagementId={E} /> }]);
    const role = await screen.findByLabelText("Role for Sam Senior");
    fireEvent.change(role, { target: { value: "staff" } });
    const dialog = await screen.findByRole("dialog", { name: "Change Sam Senior's role?" });
    expect(dialog).toBeTruthy();
    expect(sent(calls, "PUT")).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: "Change role" }));
    await waitFor(() => {
      expect(sent(calls, "PUT")).toBe(1);
    });
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.body).toEqual({ role: "staff" });
  });

  it("ac7 a cancelled role change sends nothing", async () => {
    const { calls } = api(me("u-p", "Pat Partner"));
    renderRoutes([{ path: "/", component: () => <People engagementId={E} /> }]);
    const role = await screen.findByLabelText("Role for Sam Senior");
    fireEvent.change(role, { target: { value: "reviewer" } });
    await screen.findByRole("dialog", { name: "Change Sam Senior's role?" });
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    expect(sent(calls, "PUT")).toBe(0);
  });

  it("ac7 adds a person only from the dialog's confirmation", async () => {
    const { calls } = api(me("u-p", "Pat Partner"));
    renderRoutes([{ path: "/", component: () => <People engagementId={E} /> }]);
    fireEvent.click(await screen.findByRole("button", { name: "Add person" }));
    expect(await screen.findByRole("dialog", { name: "Add a person to the team" })).toBeTruthy();
    fireEvent.click(await screen.findByLabelText("Nia New"));
    expect(sent(calls, "POST")).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: "Add to team" }));
    await waitFor(() => {
      expect(sent(calls, "POST")).toBe(1);
    });
  });
});
