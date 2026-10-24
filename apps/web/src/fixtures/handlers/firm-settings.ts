// Fixture handlers for the firm-settings family (G-01-T06; docs/contracts/firm-settings.md): the
// overview and sections (ADM-01), people and role templates (ADM-02), offices and teams. Each
// answers as the live route does for the viewer the scenario names; a save bumps the section's
// version, an empty display name answers 422, and inviting with every seat held answers 409.

import type { AnnualIndependenceOut, MeOut, SettingsPatchIn } from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { getSeed, meFor } from "../seed";
import {
  type PeopleSnapshot,
  SECTION_VALUES,
  type SectionKey,
  type SettingsViewer,
  firmOffices,
  firmTeams,
  personOut,
  roleTemplatesOut,
  settingsOverview,
  settingsSection,
  staffList,
  staffRows,
  tallies,
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
    "GET /v1/firm/staff": ({ query }) =>
      json(
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
