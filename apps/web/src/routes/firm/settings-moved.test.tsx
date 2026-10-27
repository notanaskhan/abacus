// G-01-T07 (DEC-113): a legacy /admin page whose /settings page is built redirects to it while that
// page's flag is on, and keeps the legacy page while it is off; Users & roles in the firm menu
// follows `firm_settings.v2` as Firm settings does (DEC-463).
import type { CapabilitiesOut } from "@abacus/api-client";
import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { adminRows } from "../../shell/firm/FirmMenu";
import { json, mockApi, renderRoutes } from "../../testing/support";
import { Moved } from "./settings";

afterEach(cleanup);

function caps(flags: Record<string, boolean>): CapabilitiesOut {
  return {
    engagement_id: null,
    capabilities: [],
    roles: [],
    flags,
    entitlements: [],
    office_id: null,
    tz: "America/Chicago",
    mfa_recent_until: null,
    server_now: "2026-10-22T15:00:00Z",
    clock_mode: "real",
    portal: null,
  };
}

function open(flags: Record<string, boolean>): void {
  mockApi({ "GET /v1/me/capabilities": () => json(caps(flags)) });
  renderRoutes(
    [
      {
        path: "/admin/people",
        component: () => (
          <Moved flag="firm_settings.v2" to="/settings/people">
            <p>legacy people</p>
          </Moved>
        ),
      },
      { path: "/settings/people", component: () => <p>ADM-02 people</p> },
    ],
    { at: "/admin/people" },
  );
}

describe("legacy settings paths (G-01-T07)", () => {
  it("redirect to the /settings page while its flag is on", async () => {
    open({ "firm_settings.v2": true });
    expect(await screen.findByText("ADM-02 people")).toBeTruthy();
    expect(screen.queryByText("legacy people")).toBeNull();
  });

  it("keep the legacy page while the flag is off", async () => {
    open({ "firm_settings.v2": false });
    expect(await screen.findByText("legacy people")).toBeTruthy();
    expect(screen.queryByText("ADM-02 people")).toBeNull();
  });

  it("move Users & roles in the firm menu with Firm settings", () => {
    const nav = { firm_settings: "write", users_roles: "write", audit_log: "read" } as const;
    const path = (on: boolean): (string | null)[] => adminRows(nav, on).map((r) => r.path);
    expect(path(false)).toEqual(["/admin/methodology", "/admin/people", "/admin/audit-log"]);
    expect(path(true)).toEqual(["/settings/general", "/settings/people", "/admin/audit-log"]);
  });
});
