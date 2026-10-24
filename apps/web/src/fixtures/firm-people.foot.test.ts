// G-01-T06 footing (G-01 §5.3): every ADM-01 and ADM-02 figure the fixtures show is a passing
// seed test, typed from the ADM-01 and ADM-02 specs, with no 47th name. Mirrors the Python
// slice's tests (backend/tests/unit/scenarios/test_people_slice.py).

import { describe, expect, it } from "vitest";
import { SEATS } from "./seed/people";
import {
  GROUPS,
  firmOffices,
  firmTeams,
  personOut,
  roleTemplatesOut,
  seatOf,
  settingsOverview,
  settingsSection,
  staffList,
  staffRows,
  userIdOf,
} from "./seed/firm-people";

describe("ADM-02 people foot to 46", () => {
  it("bands 7 + 7 + 11 + 14 + 5 + 2 in the screen's order (a)", () => {
    const list = staffList("e0");
    expect(list.total).toBe(46);
    expect(list.counts).toEqual({
      partners: 7,
      managers: 7,
      seniors: 11,
      staff: 14,
      seasonal: 5,
      operations: 2,
    });
    expect(list.items.map((r) => r.display_name)).toEqual(SEATS.map((s) => s.name));
    expect(list.tallies).toMatchObject({
      seats_used: 46,
      seats_total: 46,
      seats_pending: 0,
      partners: 7,
      professionals: 37,
      operations: 2,
      sso_mfa: 46,
      walls_active: 3,
      seasonal: 5,
      seasonal_access_ends_on: "2026-10-31",
    });
  });

  it("templates 7 + 4 + 6 + 8 + 8 + 11 + 1 + 1 and a locked agent row (b)", () => {
    const out = roleTemplatesOut("e0");
    expect(out.templates.map((t) => t.member_count)).toEqual([7, 4, 6, 8, 8, 11, 1, 1]);
    expect(out.grid).toHaveLength(17);
    const agent = out.grid[16];
    expect(agent?.locked).toBe(true);
    expect(new Set(Object.values(agent?.cells ?? {}))).toEqual(new Set(["locked"]));
  });

  it("teams 16 + 21 + 7 + 2, groups 2, 5 and 5, offices 22 + 14 + 10", () => {
    const teams = Object.fromEntries(firmTeams().map((t) => [t.name, t.member_ids.length]));
    expect(teams).toEqual({
      "Audit & assurance": 16,
      Tax: 21,
      "Client accounting": 7,
      "Firm operations": 2,
      "EQR pool": 2,
      "Monitoring reviewers": 5,
      Seasonal: 5,
    });
    expect(Object.keys(GROUPS)).toHaveLength(3);
    const offices = firmOffices("e0");
    expect(offices.map((o) => [o.name, o.code, o.seats, o.facts?.returns])).toEqual([
      ["Chicago", "CHI", 22, 98],
      ["Denver", "DEN", 14, 64],
      ["New York", "NYC", 10, 62],
    ]);
    expect(offices.reduce((n, o) => n + (o.facts?.returns ?? 0), 0)).toBe(224);
  });

  it("after the season: five deactivated Oct 31 and 41 of 46 (e)", () => {
    const rows = staffRows("after-season");
    const gone = rows.filter((r) => r.status === "deactivated");
    expect(gone.map((r) => r.display_name)).toEqual([
      "Lena Park",
      "Maya Adler",
      "Paige Sutton",
      "Noel Kirby",
      "Remy Vidal",
    ]);
    expect(gone.every((r) => r.deactivated_on === "2026-10-31")).toBe(true);
    expect(staffList("after-season").tallies.seats_used).toBe(41);
  });

  it("Jan 5, 2026: Lena Park's invite is the one pending, no 47th name (f)", () => {
    const list = staffList("pending-invite");
    const pending = list.items.filter((r) => r.status === "invited");
    expect(pending.map((r) => [r.display_name, r.invitation_expires_on])).toEqual([
      ["Lena Park", "2026-01-19"],
    ]);
    expect(list.tallies).toMatchObject({ seats_used: 46, seats_pending: 1 });
    expect(new Set(list.items.map((r) => r.display_name))).toEqual(
      new Set(SEATS.map((s) => s.name)),
    );
  });

  it("Lena Park's drawer: seasonal, Denver, Oct 31, one wall, three sign-ins (d)", () => {
    const lena = personOut(userIdOf(seatOf("LP")));
    expect(lena?.row).toMatchObject({
      role_template: "tax_preparer",
      level: "seasonal",
      access_ends_on: "2026-10-31",
      offshore: false,
    });
    expect(lena?.wall_ids).toHaveLength(1);
    expect(lena?.assignment_count).toBe(3);
    expect(lena?.recent_sign_ins?.map((s) => s.at)).toEqual([
      "2026-09-14T08:18:00-05:00",
      "2026-09-11T16:40:00-05:00",
      "2026-09-10T08:05:00-05:00",
    ]);
  });
});

describe("ADM-01's overview and sections", () => {
  it("shows eleven At a glance rows; People reads 46 of 46 · 0 pending (a)", () => {
    const view = settingsOverview("admin");
    expect(view.at_a_glance).toHaveLength(11);
    expect(view.at_a_glance[0]).toMatchObject({
      key: "people",
      facts: { used: 46, total: 46, pending: 0 },
    });
  });

  it("a security admin gets no Plan & seats and Security first (e)", () => {
    const view = settingsOverview("security");
    expect(view.at_a_glance[0]?.key).toBe("security");
    expect(view.sections.find((s) => s.key === "plan")?.visible).toBe(false);
    expect(settingsSection("plan", "security")).toBeUndefined();
  });

  it("a partner reads every value locked (d)", () => {
    const profile = settingsSection("profile", "partner");
    expect(profile?.read_only_reason).toBe("firm_admin_only");
    expect(profile?.values.every((v) => !v.editable)).toBe(true);
    expect(profile?.allowed_actions).toEqual([]);
  });
});
