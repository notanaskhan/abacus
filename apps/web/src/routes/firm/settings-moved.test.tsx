// G-01-T07 (DEC-113): a legacy /admin page whose /settings page is built lands on it. People and
// walls redirect for every firm since G-01-T17 retired `firm_settings.v2` (DEC-594); the audit log
// redirects while `audit_log.explorer` is on and keeps the legacy page while it is off; Users &
// roles in the firm menu opens ADM-02 as Firm settings opens ADM-01 (DEC-463).
import type { CapabilitiesOut } from "@abacus/api-client";
import { Navigate } from "@tanstack/react-router";
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

function openAuditLog(flags: Record<string, boolean>): void {
  mockApi({ "GET /v1/me/capabilities": () => json(caps(flags)) });
  renderRoutes(
    [
      {
        path: "/admin/audit-log",
        component: () => (
          <Moved flag="audit_log.explorer" to="/settings/audit-log">
            <p>legacy audit log</p>
          </Moved>
        ),
      },
      { path: "/settings/audit-log", component: () => <p>ADM-07 audit log</p> },
    ],
    { at: "/admin/audit-log" },
  );
}

describe("legacy settings paths (G-01-T07)", () => {
  it("redirect people to /settings for every firm (no flag since DEC-594)", async () => {
    mockApi({ "GET /v1/me/capabilities": () => json(caps({})) });
    renderRoutes(
      [
        { path: "/admin/people", component: () => <Navigate to="/settings/people" replace /> },
        { path: "/settings/people", component: () => <p>ADM-02 people</p> },
      ],
      { at: "/admin/people" },
    );
    expect(await screen.findByText("ADM-02 people")).toBeTruthy();
  });

  it("redirect the audit log to /settings while its flag is on", async () => {
    openAuditLog({ "audit_log.explorer": true });
    expect(await screen.findByText("ADM-07 audit log")).toBeTruthy();
    expect(screen.queryByText("legacy audit log")).toBeNull();
  });

  it("keep the legacy audit log while the flag is off", async () => {
    openAuditLog({ "audit_log.explorer": false });
    expect(await screen.findByText("legacy audit log")).toBeTruthy();
    expect(screen.queryByText("ADM-07 audit log")).toBeNull();
  });

  it("open Users & roles in the firm menu on ADM-02, as Firm settings opens ADM-01", () => {
    const nav = { firm_settings: "write", users_roles: "write", audit_log: "read" } as const;
    expect(adminRows(nav).map((r) => r.path)).toEqual([
      "/settings/general",
      "/settings/people",
      "/admin/audit-log",
    ]);
  });
});
