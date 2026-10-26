// Fixture handlers for the firm-settings family (G-01-T06; docs/contracts/firm-settings.md): the
// overview and sections (ADM-01), people and role templates (ADM-02), offices and teams. Each
// answers as the live route does for the viewer the scenario names; a save bumps the section's
// version, an empty display name answers 422, and inviting with every seat held answers 409.

import type {
  AnnualIndependenceOut,
  FirmOfficeIn,
  FirmOfficeOut,
  MeOut,
  PersonPatchIn,
  ServiceLinePolicyIn,
  ServiceLinePolicyOut,
  SettingsPatchIn,
  WallIn,
  WallOut,
  WallPreviewOut,
} from "@abacus/api-client";
import { nowMs } from "../../app-core/clock";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { getSeed, meFor } from "../seed";
import {
  ASHFORD_CLIENT,
  ASHFORD_PARTNER,
  ASHFORD_WALL,
  type PeopleSnapshot,
  SECTION_VALUES,
  type SectionKey,
  type SettingsViewer,
  firmOffices,
  firmTeams,
  firmWalls,
  personOut,
  offshoreGroup,
  roleTemplatesOut,
  seatOf,
  serviceLinePolicies,
  settingsOverview,
  settingsSection,
  staffList,
  staffRows,
  tallies,
  userIdOf,
  type WallState,
  wallEvents,
} from "../seed/firm-people";

const NOT_FOUND = { detail: "not found" };
const SECTIONS = new Set<string>(["profile", "defaults", "plan"]);

/** `/v1/me` with the firm role the people slice gives (Felix Andersen: `security_admin`). */
export function meAs(persona: string): MeOut | undefined {
  const me = meFor(getSeed(), persona);
  if (me === undefined || persona !== "felix-andersen") return me;
  return {
    ...me,
    memberships: me.memberships.map((m) => ({ ...m, firm_role: "security_admin" })),
  };
}

export function firmSettingsHandlers(
  viewer: SettingsViewer,
  snapshot: PeopleSnapshot = "e0",
): Record<string, FixtureHandler> {
  const values: Record<string, Record<string, string | number | boolean | null>> = {
    profile: { ...SECTION_VALUES.profile },
    defaults: { ...SECTION_VALUES.defaults },
    plan: { ...SECTION_VALUES.plan },
  };
  const versions: Record<string, number> = { profile: 1, defaults: 1, plan: 1 };
  const section = (key: string) =>
    SECTIONS.has(key)
      ? settingsSection(key as SectionKey, viewer, values[key], versions[key])
      : undefined;
  return {
    "GET /v1/me": ({ persona }) => {
      const me = meAs(persona ?? "grace-holloway");
      return me === undefined ? json({ detail: "unknown_persona" }, 404) : json(me);
    },
    "GET /v1/firm/settings/overview": () => json(settingsOverview(viewer)),
    "GET /v1/firm/settings/{section}": ({ params }) => {
      const found = section(params.section ?? "");
      return found === undefined ? json(NOT_FOUND, 404) : json(found);
    },
    "PATCH /v1/firm/settings/{section}": ({ params, body }) => {
      const key = params.section ?? "";
      if (viewer !== "admin") return json({ detail: "forbidden" }, 403);
      const found = section(key);
      if (found === undefined) return json(NOT_FOUND, 404);
      const patch = body as SettingsPatchIn;
      if (patch.version !== versions[key]) {
        return json({ detail: "stale_version", facts: { section: key } }, 409);
      }
      const name = patch.values.display_name;
      if (name !== undefined && (name === null || String(name).trim() === "")) {
        return json({ detail: "display_name_required" }, 422);
      }
      values[key] = { ...values[key], ...patch.values };
      versions[key] = (versions[key] ?? 1) + 1;
      return json(section(key));
    },
    "GET /v1/firm/offices": () => json(firmOffices(snapshot)),
    "GET /v1/firm/teams": () => json(firmTeams()),
    "GET /v1/firm/role-templates": () => json(roleTemplatesOut(snapshot)),
    "GET /v1/firm/staff/{user_id}": ({ params }) => {
      const found = personOut(params.user_id ?? "", snapshot);
      return found === undefined ? json(NOT_FOUND, 404) : json(found);
    },
    "GET /v1/walls": () => json(firmWalls()),
    // AC4.6 with no consent provider (DEC-286): offshore on over assignments is refused.
    "PATCH /v1/firm/staff/{user_id}": ({ params, body }) => {
      if (viewer !== "admin") return json({ detail: "forbidden" }, 403);
      const found = personOut(params.user_id ?? "", snapshot);
      if (found === undefined) return json(NOT_FOUND, 404);
      const patch = body as PersonPatchIn;
      if (patch.version !== found.version) return json({ detail: "stale_version" }, 409);
      if (patch.offshore === true && (found.assignment_count ?? 0) > 0) {
        return json(
          {
            detail: "offshore_assignment_conflict",
            facts: { assignments: found.assignment_count },
          },
          409,
        );
      }
      return json({
        ...found,
        row: { ...found.row, offshore: patch.offshore ?? found.row.offshore },
        version: found.version + 1,
      });
    },
    "PUT /v1/firm/staff/{user_id}/role": ({ params }) =>
      viewer === "admin" ? json({ id: params.user_id ?? "" }) : json({ detail: "forbidden" }, 403),
    "POST /v1/firm/staff/{user_id}/deactivate": ({ params }) => {
      if (viewer !== "admin") return json({ detail: "forbidden" }, 403);
      const found = personOut(params.user_id ?? "", snapshot);
      if (found === undefined) return json(NOT_FOUND, 404);
      return json({
        ...found,
        row: { ...found.row, status: "deactivated", allowed_actions: [] },
      });
    },
    // DEC-286: the list stays on `firm.manage_users`, so a partner or security admin is refused.
    "GET /v1/firm/staff": ({ query }) =>
      viewer !== "admin"
        ? json({ detail: "forbidden" }, 403)
        : json(
            staffList(snapshot, {
              q: query.get("q"),
              role_template: query.get("role_template"),
              office_id: query.get("office_id"),
              team_id: query.get("team_id"),
              status: query.get("status"),
              band: query.get("band"),
            }),
          ),
    "POST /v1/firm/staff/invitations": () => {
      const t = tallies(staffRows(snapshot));
      const total = t.seats_total ?? 0;
      return t.seats_used >= total
        ? json({ detail: "seats_full", facts: { used: t.seats_used, total } }, 409)
        : json({ id: "00000000-0000-4000-8000-000000000001" }, 201);
    },
    "GET /v1/firm/independence/annual": ({ query }) => {
      // DF-07 has no design data: every seat holder reads "Not yet" until confirmations exist.
      const rows = staffRows(snapshot).filter((r) => r.status === "active");
      const body: AnnualIndependenceOut = {
        year: Number(query.get("year") ?? 2026),
        rows: rows.map((r) => ({ user_id: r.user_id ?? "", status: "not_yet" })),
        counts: { confirmed: 0, not_yet: rows.length, declined: 0 },
      };
      return json(body);
    },
  };
}

// --- ADM-03: offices, teams, service lines, walls and offshore (G-01-T14) -----------------------

export interface Adm03Options {
  /** The viewer's initials: rows carry their wall actions (Approve, Lift). */
  viewer: string;
  /** May the viewer edit offices, teams and service lines (firm or security admin)? */
  manage: boolean;
  /** Lena Park's wall: awaiting Margaret Okonkwo, or approved (ADM-03g). */
  wallState?: WallState;
  /** ADM-03d: Remy Vidal is in the offshore group. */
  offshoreRemy?: boolean;
  /** ADM-03b: 9:20 AM, the moment before Grace adds the Lena Park ✕ Ashford wall. */
  beforeLenaWall?: boolean;
}

/** The live routes' answers for ADM-03 (docs/contracts/firm-settings.md): a save bumps the
 * version, Audit can't be widened (422 `audit_locked`), a relationship partner or a duplicate
 * can't be walled (409), and only the named partner approves. */
export function adm03Handlers(options: Adm03Options): Record<string, FixtureHandler> {
  const forbidden = () => json({ detail: "forbidden" }, 403);
  const lines = serviceLinePolicies();
  const offices = firmOffices("e0", true);
  const created: WallOut[] = [];
  const walls = (): WallOut[] => [
    ...firmWalls(options.wallState, options.viewer).filter(
      (w) => options.beforeLenaWall !== true || w.id !== ASHFORD_WALL,
    ),
    ...created,
  ];
  const ashfordPartner = userIdOf(seatOf(ASHFORD_PARTNER));
  const blockers = (user: string, client: string): WallPreviewOut["blockers"] => [
    ...(client === ASHFORD_CLIENT && user === ashfordPartner
      ? (["relationship_partner"] as const)
      : []),
    ...(walls().some((w) => w.user_id === user && w.client_id === client && w.status === "active")
      ? (["wall_exists"] as const)
      : []),
  ];
  return {
    "GET /v1/firm/offices": () => json(offices),
    "GET /v1/firm/teams": () => json(firmTeams({ pools: true })),
    "PATCH /v1/firm/offices/{office_id}": ({ params, body }) => {
      if (!options.manage) return forbidden();
      const i = offices.findIndex((o) => o.id === params.office_id);
      const found = offices[i];
      if (found === undefined) return json(NOT_FOUND, 404);
      const patch = body as FirmOfficeIn;
      if (patch.version !== found.version) return json({ detail: "stale_version" }, 409);
      const next: FirmOfficeOut = {
        ...found,
        ...patch,
        is_hq: patch.is_hq ?? found.is_hq,
        version: (found.version ?? 1) + 1,
      };
      offices[i] = next;
      return json(next);
    },
    "GET /v1/firm/service-lines": () => json(lines),
    "PUT /v1/firm/service-lines/{line}": ({ params, body }) => {
      if (!options.manage) return forbidden();
      const i = lines.findIndex((l) => l.service_line === params.line);
      const found = lines[i];
      if (found === undefined) return json(NOT_FOUND, 404);
      const patch = body as ServiceLinePolicyIn;
      if (found.service_line === "audit" && patch.content_visible_to !== "engagement_team_only") {
        return json({ detail: "audit_locked", facts: { service_line: "audit" } }, 422);
      }
      if (patch.version !== found.version) {
        return json({ detail: "stale_version", facts: { version: found.version } }, 409);
      }
      const next: ServiceLinePolicyOut = { ...found, ...patch, version: found.version + 1 };
      lines[i] = next;
      return json(next);
    },
    "GET /v1/firm/offshore": () => json(offshoreGroup(options.offshoreRemy === true)),
    "GET /v1/walls": () => json(walls()),
    "GET /v1/walls/preview": ({ query }) => {
      const body: WallPreviewOut = {
        blockers: blockers(query.get("user_id") ?? "", query.get("client_id") ?? ""),
        assignments_ended: 0,
      };
      return json(body);
    },
    "POST /v1/walls": ({ body }) => {
      const wall = body as WallIn;
      const found = blockers(wall.user_id, wall.client_id);
      if (found.length > 0) return json({ detail: found[0] }, 409);
      const out: WallOut = {
        id: `00000000-0000-4000-8000-${String(created.length + 1).padStart(12, "0")}`,
        user_id: wall.user_id,
        client_id: wall.client_id,
        reason_code: wall.reason_code ?? "other",
        reason_text: wall.reason_text ?? null,
        created_by: userIdOf(seatOf(options.viewer)),
        created_at: new Date(nowMs()).toISOString(),
        approver_user_id: wall.approver_user_id ?? null,
        approval_status: "awaiting",
        approved_at: null,
        status: "active",
        removed_at: null,
        removed_by: null,
        removed_reason: null,
        allowed_actions: [],
      };
      created.push(out);
      return json(out, 201);
    },
    "POST /v1/walls/{wall_id}/approve": ({ params }) => {
      const found = walls().find((w) => w.id === params.wall_id);
      if (found === undefined) return json(NOT_FOUND, 404);
      if (!(found.allowed_actions ?? []).includes("wall.approve")) {
        return json({ detail: "not_named_approver" }, 403);
      }
      return json({
        ...found,
        approval_status: "approved",
        approved_at: new Date(nowMs()).toISOString(),
      });
    },
    "POST /v1/walls/{wall_id}/remove": ({ params }) => {
      const found = walls().find((w) => w.id === params.wall_id);
      if (found === undefined) return json(NOT_FOUND, 404);
      if (!(found.allowed_actions ?? []).includes("wall.remove")) return forbidden();
      return json({ ...found, status: "removed", removed_at: new Date(nowMs()).toISOString() });
    },
    "GET /v1/walls/{wall_id}/events": ({ params }) =>
      json({
        items: wallEvents(params.wall_id ?? "", options.wallState),
        next_cursor: null,
        total: wallEvents(params.wall_id ?? "", options.wallState).length,
      }),
  };
}
