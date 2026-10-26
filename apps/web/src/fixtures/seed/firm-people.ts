// The firm's people, offices, teams and settings for ADM-01 and ADM-02 (G-01-T06; G-01 §5.3).
// Mirrors the Python `people` slice (backend/.../brightwater_hale/firm_people.py): the same
// templates, levels, titles, teams and seasonal end for the 46 seats, the same seat total. Data
// the live seed can't hold yet is fixture-only here and says so: last-active times and Lena
// Park's sign-ins (ADM-02 spec), the groups (G-01-T08), office codes, addresses and returns
// (T08, T-02), the walls' tags (T09), the Nov 2 deactivations (T13's job), Lena Park's Jan 5,
// 2026 invitation (before the firm's setup on the timeline), the eleven At a glance rows and the
// later epics' defaults (AC2.2: fixture mode renders them all for parity).

import type {
  FirmOfficeOut,
  FirmTeamOut,
  OffshoreOut,
  ServiceLinePolicyOut,
  WallEventOut,
  GlanceRowOut,
  GridRowOut,
  PersonOut,
  RoleTemplatesOut,
  SettingValueOut,
  SettingsOverviewOut,
  SettingsSectionValuesOut,
  StaffListOut,
  StaffRowV2Out,
  StaffTalliesOut,
  WallOut,
} from "@abacus/api-client";
import { ROLE_TEMPLATES } from "../../app-core/roleTemplates.gen";
import { slugOfClient } from "./clients";
import { JOB_TITLES, OFFICES, SEATS, type Seat, type SeatRole, emailOf, slugOf } from "./people";
import { stableId } from "./prng";

export type Template = StaffRowV2Out["role_template"];
export type Level = StaffRowV2Out["level"];
export type Band = StaffRowV2Out["band"];
export type TeamName = "Audit & assurance" | "Tax" | "Client accounting" | "Firm operations";
/** E0; Mon Nov 2, 2026 after the access-end job (ADM-02e); Mon Jan 5, 2026 (ADM-02f). */
export type PeopleSnapshot = "e0" | "after-season" | "pending-invite";

export const SEATS_TOTAL = 46;
export const SEASON_ENDS = "2026-10-31";
export const SEATLESS_STAFF = 6; // ADM-01 C: "6 back-office staff hold no seat"

export const TEMPLATE_OF_ROLE: Readonly<Record<SeatRole, Template>> = {
  Partner: "partner",
  Manager: "manager",
  "Tax Reviewer": "tax_reviewer",
  Senior: "senior",
  Staff: "staff",
  "Tax Preparer": "tax_preparer",
  "Firm Admin": "firm_admin",
  "IT / Security": "it_security",
};
/** ADM-02a's bands in order with their row counts; the band is the level. */
export const BANDS: readonly (readonly [Level, Band, number])[] = [
  ["partner", "partners", 7],
  ["manager", "managers", 7],
  ["senior", "seniors", 11],
  ["staff", "staff", 14],
  ["seasonal", "seasonal", 5],
  ["admin", "operations", 2],
];
export const TEAMS: readonly TeamName[] = [
  "Audit & assurance",
  "Tax",
  "Client accounting",
  "Firm operations",
];
const NOT_TAX: Readonly<Record<Exclude<TeamName, "Tax">, readonly string[]>> = {
  "Audit & assurance": [
    ...["MO", "TW", "CM", "HL", "LK", "OH", "MD", "CD", "JB", "SB"],
    ...["AC", "AW", "FN", "KR", "CH", "HP"],
  ],
  "Client accounting": ["PR", "HV", "RM", "EW", "RF", "IV", "EG"],
  "Firm operations": ["GH", "FA"],
};
const SERVICE_LINE: Readonly<Record<TeamName, "audit" | "tax" | "cas" | null>> = {
  "Audit & assurance": "audit",
  Tax: "tax",
  "Client accounting": "cas",
  "Firm operations": null,
};
/** ADM-03a's groups (G-01-T08 loads them once teams have kinds). */
export const GROUPS: Readonly<Record<string, readonly string[]>> = {
  "EQR pool": ["TW", "CM"],
  "Monitoring reviewers": ["TW", "CM", "LK", "IM", "TR"],
  Seasonal: ["LP", "MA", "PS", "NK", "RV"],
};
const GROUP_KIND: Readonly<Record<string, FirmTeamOut["kind"]>> = {
  "EQR pool": "eqr_pool",
  "Monitoring reviewers": "monitoring_reviewers",
  Seasonal: "custom",
};
/** ADM-02a's "Wall 1" tags (ADM-03's three walls; reasons and approvers arrive with T09). */
export const WALLED: readonly string[] = ["VH", "LP", "PS"];

/** ADM-02a's Last active at E0 (CT). Rows shown only as a day take noon (fixture-only). */
const LAST_ACTIVE: Readonly<Record<string, string>> = {
  ...{ MO: "09:10", DR: "09:24", PR: "08:47", TW: "09-11", VH: "08:15", CM: "09:02" },
  ...{ NA: "07:58", HL: "09:21", SI: "09:05", LK: "08:33", OH: "09-13", IM: "08:41" },
  ...{ TR: "09:14", HV: "08:20", OB: "09:19", MD: "09:24", RM: "09:18", CD: "08:52" },
  ...{ JB: "09-11", SB: "08:10", YK: "09:11", NP: "08:58", QL: "09:07", EW: "08:29" },
  ...{ RF: "08:44", AC: "09:16", KO: "09:12", AW: "08:39", FN: "09:01", KR: "09-11" },
  ...{ CH: "08:06", HP: "08:55", BN: "09:09", GT: "08:27", JL: "08:12", LW: "07:49" },
  ...{ DS: "09:15", IV: "08:36", EG: "08:03", LP: "08:18", MA: "08:50", PS: "09-12" },
  ...{ NK: "07:55", RV: "09:03", GH: "09:24", FA: "09:20" },
};

export function userIdOf(seat: Seat): string {
  return stableId(`user:${slugOf(seat.name)}`);
}
export function officeIdOf(name: string): string {
  return stableId(`office:${name}`);
}
export function teamIdOf(name: string): string {
  return stableId(`team:${name}`);
}
export function seatOf(initials: string): Seat {
  const seat = SEATS.find((s) => s.initials === initials);
  if (seat === undefined) throw new Error(`no seat ${initials}`);
  return seat;
}

export function levelOf(seat: Seat): Level {
  let end = 0;
  for (const [level, , size] of BANDS) {
    end += size;
    if (seat.n <= end) return level;
  }
  throw new Error(`seat ${String(seat.n)} is outside the 46`);
}
export function bandOf(level: Level): Band {
  return BANDS.find(([l]) => l === level)?.[1] ?? "staff";
}
export function teamOf(seat: Seat): TeamName {
  for (const [team, members] of Object.entries(NOT_TAX)) {
    if (members.includes(seat.initials)) return team as TeamName;
  }
  return "Tax";
}
/** One title per person: SHL-03's where it gives one (`/v1/me`), else ADM-02's line. */
export function titleOf(seat: Seat): string {
  return JOB_TITLES[seat.initials] ?? seat.title;
}
function lastActive(initials: string): string | null {
  const at = LAST_ACTIVE[initials];
  if (at === undefined) return null;
  return at.includes(":")
    ? `2026-09-14T${at}:00-05:00`
    : `2026-${at.slice(0, 2)}-${at.slice(3)}T12:00:00-05:00`;
}

const FIRM_ROLE: Readonly<Record<string, string>> = {
  GH: "firm_admin",
  FA: "security_admin",
  MO: "practice_leader",
  TW: "quality_partner",
};
const MANAGE = ["firm.manage_users", "security_role.assign"];
/** Who holds `security_admin` (the people slice gives Felix Andersen IT / Security). */
const SECURITY_ADMINS = new Set(["FA"]);

function rowOf(seat: Seat, snapshot: PeopleSnapshot): StaffRowV2Out {
  const level = levelOf(seat);
  const team = teamOf(seat);
  const line = SERVICE_LINE[team];
  const seasonal = level === "seasonal";
  const gone = snapshot === "after-season" && seasonal;
  const groups = Object.entries(GROUPS)
    .filter(([, members]) => members.includes(seat.initials))
    .map(([name]) => teamIdOf(name));
  return {
    user_id: userIdOf(seat),
    invitation_id: null,
    display_name: seat.name,
    email: emailOf(seat.name),
    title: titleOf(seat),
    role_template: TEMPLATE_OF_ROLE[seat.role],
    level,
    band: bandOf(level),
    status: gone ? "deactivated" : "active",
    office_id: officeIdOf(seat.office),
    team_ids: [teamIdOf(team), ...groups],
    service_lines: line === null ? [] : [line],
    access_ends_on: seasonal ? SEASON_ENDS : null,
    offshore: false,
    last_sign_in_at: snapshot === "e0" ? lastActive(seat.initials) : null,
    invitation_expires_on: null,
    deactivated_on: gone ? SEASON_ENDS : null,
    allowed_actions: gone ? [] : MANAGE,
  };
}

/** ADM-02f: Lena Park invited Mon Jan 5, 2026, 14 days (DEC-35); no 47th name. */
export const LENA_INVITATION = stableId("staff-invitation:lena-park:2026-01-05");

export function staffRows(snapshot: PeopleSnapshot = "e0"): StaffRowV2Out[] {
  return SEATS.map((seat) => {
    const row = rowOf(seat, snapshot);
    if (snapshot !== "pending-invite" || seat.initials !== "LP") return row;
    return {
      ...row,
      user_id: null,
      invitation_id: LENA_INVITATION,
      status: "invited",
      team_ids: [teamIdOf("Tax")],
      last_sign_in_at: null,
      invitation_expires_on: "2026-01-19",
      allowed_actions: ["firm.manage_users"],
    };
  });
}

export function tallies(rows: readonly StaffRowV2Out[]): StaffTalliesOut {
  const active = rows.filter((r) => r.status === "active");
  const pending = rows.filter((r) => r.status === "invited").length;
  const partners = active.filter((r) => r.level === "partner").length;
  const operations = active.filter((r) => r.level === "admin").length;
  const seasonal = active.filter((r) => r.level === "seasonal");
  return {
    seats_used: active.length + pending,
    seats_total: SEATS_TOTAL,
    seats_pending: pending,
    partners,
    professionals: active.length - partners - operations,
    operations,
    sso_mfa: active.length,
    signed_in_of: active.length,
    walls_active: WALLED.length,
    seasonal: seasonal.length,
    seasonal_access_ends_on: seasonal.length > 0 ? SEASON_ENDS : null,
  };
}

export interface StaffQuery {
  q?: string | null;
  role_template?: string | null;
  office_id?: string | null;
  team_id?: string | null;
  status?: string | null;
  band?: string | null;
}

/** `GET /v1/firm/staff` as the live service answers it: bands in order, counts per band over
 * the filters less the band filter, firm-wide tallies, SPEC-024's legacy lists. */
export function staffList(snapshot: PeopleSnapshot = "e0", query: StaffQuery = {}): StaffListOut {
  const rows = staffRows(snapshot);
  const needle = query.q?.toLowerCase() ?? "";
  const unbanded = rows.filter(
    (r) =>
      (needle === "" ||
        r.display_name.toLowerCase().includes(needle) ||
        r.email.toLowerCase().includes(needle)) &&
      (query.role_template == null || r.role_template === query.role_template) &&
      (query.office_id == null || r.office_id === query.office_id) &&
      (query.team_id == null || (r.team_ids ?? []).includes(query.team_id)) &&
      (query.status == null || r.status === query.status),
  );
  const counts = Object.fromEntries(
    BANDS.map(([, band]) => [band, unbanded.filter((r) => r.band === band).length]),
  );
  const items = unbanded.filter((r) => query.band == null || r.band === query.band);
  return {
    items,
    total: items.length,
    counts,
    tallies: tallies(rows),
    members: rows
      .filter((r) => r.user_id !== null)
      .map((r) => ({
        user_id: r.user_id ?? "",
        display_name: r.display_name,
        email: r.email,
        firm_role: (FIRM_ROLE[seatByName(r.display_name).initials] ??
          null) as StaffListOut["members"][number]["firm_role"],
        status: r.status === "active" ? "active" : "revoked",
      })),
    invitations: rows
      .filter((r) => r.invitation_id != null)
      .map((r) => ({
        id: r.invitation_id ?? "",
        email: r.email,
        firm_role: null,
        expires_at: "2026-01-19T10:12:00-06:00",
        created_at: "2026-01-05T10:12:00-06:00",
      })),
  };
}

function seatByName(name: string): Seat {
  const seat = SEATS.find((s) => s.name === name);
  if (seat === undefined) throw new Error(`no seat ${name}`);
  return seat;
}

/** ADM-02d's three sign-ins for Lena Park, verbatim (fixture-only: no IP is stored live). */
const LENA_SIGN_INS = [
  { at: "2026-09-14T08:18:00-05:00", method: "Microsoft SSO", mfa: true, ip: "198.51.100.62" },
  { at: "2026-09-11T16:40:00-05:00", method: "Microsoft SSO", mfa: true, ip: "198.51.100.62" },
  { at: "2026-09-10T08:05:00-05:00", method: "Microsoft SSO", mfa: true, ip: "198.51.100.62" },
];
export const ASHFORD_WALL = stableId("wall:lena-park:ashford-manufacturing-co");

/** ADM-03's three walls (G-01 §5.3): person, client, reason, added, approver. Lena Park's is
 * today's, active at once and awaiting Margaret Okonkwo (DEC-73); the other two are approved. */
const WALLS: readonly {
  id: string;
  person: string;
  client: string;
  reason: WallOut["reason_code"];
  text: string;
  at: string;
  approver: string;
  approvedAt: string | null;
}[] = [
  {
    id: stableId("wall:victor-hammond:two-rivers-brewing-co"),
    person: "VH",
    client: "Two Rivers Brewing Co.",
    reason: "financial_interest",
    text: "Ownership stake",
    at: "2026-02-03T10:00:00-06:00",
    approver: "MO",
    approvedAt: "2026-02-03T10:00:00-06:00",
  },
  {
    id: ASHFORD_WALL,
    person: "LP",
    client: "Ashford Manufacturing Co.",
    reason: "personal_relationship",
    text: "Family member employed at Ashford",
    at: "2026-09-14T09:20:00-05:00",
    approver: "MO",
    approvedAt: null,
  },
  {
    id: stableId("wall:paige-sutton:harold-stein"),
    person: "PS",
    client: "Harold Stein",
    reason: "relative",
    text: "Brother-in-law",
    at: "2026-02-18T10:00:00-06:00",
    approver: "DR",
    approvedAt: "2026-02-18T10:00:00-06:00",
  },
];

/** Ashford Manufacturing Co.'s relationship partner (ADM-03c): Neil Ashcroft. */
export const ASHFORD_PARTNER = "NA";
export const ASHFORD_CLIENT = stableId(`client:${slugOfClient("Ashford Manufacturing Co.")}`);

/** Lena Park's wall before Margaret Okonkwo approves it (ADM-03a, f: "Awaiting …") or after
 * (ADM-03g: the log reads "Approved by Margaret Okonkwo", both at 9:20 AM). */
export type WallState = "awaiting" | "approved";

/** What the viewer may do with each wall (ED-071; AC11.2): Approve where they are its named
 * partner and it awaits them, Lift where they are a partner and it isn't on themself. */
function wallActions(
  w: { person: string; approver: string },
  approved: boolean,
  viewer: string | undefined,
): string[] {
  if (viewer === undefined) return [];
  const seat = SEATS.find((s) => s.initials === viewer);
  if (seat === undefined || levelOf(seat) !== "partner") return [];
  return [
    ...(!approved && w.approver === viewer ? ["wall.approve"] : []),
    ...(w.person === viewer ? [] : ["wall.remove"]),
  ];
}

/** `GET /v1/walls` (SPEC-002; G-01-T09's register) for the three walls; `viewer` is the reader's
 * initials when the rows should carry their actions. */
export function firmWalls(state: WallState = "awaiting", viewer?: string): WallOut[] {
  const grace = userIdOf(seatOf("GH"));
  return WALLS.map((w) => {
    const approvedAt = w.approvedAt ?? (state === "approved" ? w.at : null);
    return {
      id: w.id,
      user_id: userIdOf(seatOf(w.person)),
      client_id: stableId(`client:${slugOfClient(w.client)}`),
      reason_code: w.reason,
      reason_text: w.text,
      created_by: grace,
      created_at: w.at,
      approver_user_id: userIdOf(seatOf(w.approver)),
      approval_status: approvedAt === null ? "awaiting" : "approved",
      approved_at: approvedAt,
      status: "active",
      removed_at: null,
      removed_by: null,
      removed_reason: null,
      allowed_actions: wallActions(w, approvedAt !== null, viewer),
    } satisfies WallOut;
  });
}

/** `GET /v1/walls/{id}/events` (ADM-03g): newest first, in the ADM-07 grammar's event types. */
export function wallEvents(wallId: string, state: WallState = "awaiting"): WallEventOut[] {
  const w = WALLS.find((x) => x.id === wallId);
  if (w === undefined) return [];
  const approvedAt = w.approvedAt ?? (state === "approved" ? w.at : null);
  const added: WallEventOut = {
    event_type: "wall.created",
    at: w.at,
    actor_user_id: userIdOf(seatOf("GH")),
  };
  return approvedAt === null
    ? [added]
    : [
        {
          event_type: "wall.approved",
          at: approvedAt,
          actor_user_id: userIdOf(seatOf(w.approver)),
        },
        added,
      ];
}

/** ADM-03's service lines (revision R2, item 1): leads, who reads content, cross-line access. */
export function serviceLinePolicies(): ServiceLinePolicyOut[] {
  const lead = (i: string): string => userIdOf(seatOf(i));
  return [
    {
      service_line: "audit",
      enabled: true,
      lead_user_id: lead("MO"),
      content_visible_to: "engagement_team_only",
      cross_line_access: "handoffs_only",
      version: 1,
    },
    {
      service_line: "tax",
      enabled: true,
      lead_user_id: lead("DR"),
      content_visible_to: "service_line",
      cross_line_access: "handoffs_only",
      version: 1,
    },
    {
      service_line: "cas",
      enabled: true,
      lead_user_id: lead("PR"),
      content_visible_to: "service_line",
      cross_line_access: "handoffs_only",
      version: 1,
    },
    {
      service_line: "advisory",
      enabled: true,
      lead_user_id: lead("PR"),
      content_visible_to: "engagement_team_only",
      cross_line_access: "by_request",
      version: 1,
    },
  ];
}

/** `GET /v1/firm/offshore` (ADM-03d): no member at E0, Remy Vidal once he is marked offshore;
 * no client is consented until T-01 registers the provider (DEC-52). */
export function offshoreGroup(remy: boolean): OffshoreOut {
  return {
    member_ids: remy ? [userIdOf(seatOf("RV"))] : [],
    consented_client_count: 0,
    block_without_consent: true,
    mask_tins: true,
  };
}

/** `GET /v1/firm/staff/{user_id}`: ADM-02d's drawer (Lena Park's facts from the design). */
export function personOut(userId: string, snapshot: PeopleSnapshot = "e0"): PersonOut | undefined {
  const row = staffRows(snapshot).find((r) => r.user_id === userId);
  if (row === undefined) return undefined;
  const seat = seatByName(row.display_name);
  const lena = seat.initials === "LP";
  return {
    row,
    firm_role: FIRM_ROLE[seat.initials] ?? null,
    security_admin: SECURITY_ADMINS.has(seat.initials),
    wall_ids: lena ? [ASHFORD_WALL] : [],
    assignment_count: lena ? 3 : 0,
    recent_sign_ins: lena ? LENA_SIGN_INS : [],
    annual_independence: "not_yet",
    version: 1,
  };
}

/** `GET /v1/firm/role-templates`: counts from the rows, the generated grid, the locked agent. */
export function roleTemplatesOut(snapshot: PeopleSnapshot = "e0"): RoleTemplatesOut {
  const active = staffRows(snapshot).filter((r) => r.status === "active");
  const templates = Object.entries(ROLE_TEMPLATES.templates).map(([key, spec]) => ({
    key: key as Template,
    levels: [...spec.levels] as Level[],
    member_count: active.filter((r) => r.role_template === key).length,
  }));
  const grid: GridRowOut[] = ROLE_TEMPLATES.grid.map((row) => ({
    key: row.key,
    actions: [...row.actions],
    cells: { ...row.cells },
    conditions: { ...row.conditions },
    source: row.actions.length > 0 ? "matrix" : "policy",
    locked: false,
  }));
  const never = new Set<string>(ROLE_TEMPLATES.agentNever);
  grid.push({
    key: "accrued_agent",
    actions: [
      ...new Set(ROLE_TEMPLATES.grid.filter((r) => never.has(r.key)).flatMap((r) => r.actions)),
    ].sort(),
    cells: Object.fromEntries(Object.keys(ROLE_TEMPLATES.templates).map((t) => [t, "locked"])),
    conditions: {},
    source: "policy",
    locked: true,
  });
  return { templates, grid };
}

/** `GET /v1/firm/offices` (T08's shape): seats from the rows; returns are T-02's office facts. */
const OFFICE_FACTS: Readonly<
  Record<
    string,
    {
      code: string;
      zone: string;
      line1: string;
      city: string;
      region: string;
      postal: string;
      returns: number;
    }
  >
> = {
  Chicago: {
    code: "CHI",
    zone: "America/Chicago",
    line1: "311 West Brannock Street, Suite 1700",
    city: "Chicago",
    region: "IL",
    postal: "60606",
    returns: 98,
  },
  Denver: {
    code: "DEN",
    zone: "America/Denver",
    line1: "1820 Coalbank Street, Suite 400",
    city: "Denver",
    region: "CO",
    postal: "80202",
    returns: 64,
  },
  "New York": {
    code: "NYC",
    zone: "America/New_York",
    line1: "60 Quillon Place, 23rd Floor",
    city: "New York",
    region: "NY",
    postal: "10006",
    returns: 62,
  },
};

/** ADM-03a's office leads and default reviewer pools (the pool's name is what the design draws). */
const OFFICE_LEADS: Readonly<Record<string, string>> = {
  Chicago: "MO",
  Denver: "PR",
  "New York": "DR",
};
const REVIEWER_POOLS: Readonly<Record<string, readonly [string, readonly string[]]>> = {
  Chicago: ["Tax reviewers in Chicago", ["YK"]],
  Denver: ["IM, OB", ["IM", "OB"]],
  "New York": ["SI, TR, NP, QL", ["SI", "TR", "NP", "QL"]],
};

/** `GET /v1/firm/offices`; `pools` names each office's reviewer pool (ADM-03a), which the teams
 * list then carries (`firmTeams({ pools: true })`). */
export function firmOffices(snapshot: PeopleSnapshot = "e0", pools = false): FirmOfficeOut[] {
  const active = staffRows(snapshot).filter((r) => r.status !== "deactivated");
  return OFFICES.map((o) => {
    const f = OFFICE_FACTS[o.name];
    return {
      id: officeIdOf(o.name),
      name: o.name,
      code: f?.code ?? "",
      is_hq: o.hq,
      time_zone: f?.zone ?? "America/Chicago",
      address_line1: f?.line1 ?? null,
      address_line2: null,
      city: f?.city ?? null,
      region_code: f?.region ?? null,
      postal_code: f?.postal ?? null,
      lead_user_id:
        OFFICE_LEADS[o.name] === undefined ? null : userIdOf(seatOf(OFFICE_LEADS[o.name] ?? "")),
      default_reviewer_pool_team_id: pools ? teamIdOf(REVIEWER_POOLS[o.name]?.[0] ?? "") : null,
      seats: active.filter((r) => r.office_id === officeIdOf(o.name)).length,
      facts: { returns: f?.returns ?? 0 },
      allowed_actions: [],
      version: 1,
    };
  });
}

/** `GET /v1/firm/teams` (T08's shape): four service-line teams and three groups, and with `pools`
 * the three offices' reviewer pools (ADM-03a). */
export function firmTeams({ pools = false }: { pools?: boolean } = {}): FirmTeamOut[] {
  const teams: FirmTeamOut[] = TEAMS.map((name) => ({
    id: teamIdOf(name),
    name,
    kind: "service_line",
    office_id: null,
    lead_user_id: null,
    member_ids: SEATS.filter((s) => teamOf(s) === name).map(userIdOf),
    allowed_actions: [],
  }));
  for (const [name, members] of Object.entries(GROUPS)) {
    teams.push({
      id: teamIdOf(name),
      name,
      kind: GROUP_KIND[name] ?? "custom",
      office_id: null,
      lead_user_id: null,
      member_ids: members.map((i) => userIdOf(seatOf(i))),
      allowed_actions: [],
    });
  }
  if (pools) {
    for (const [name, members] of Object.values(REVIEWER_POOLS)) {
      teams.push({
        id: teamIdOf(name),
        name,
        kind: "reviewer_pool",
        office_id: null,
        lead_user_id: null,
        member_ids: members.map((i) => userIdOf(seatOf(i))),
        allowed_actions: [],
      });
    }
  }
  return teams;
}

// --- ADM-01: the overview and its sections ----------------------------------------------------

export type SettingsViewer = "admin" | "partner" | "security";

/** The eleven At a glance rows (AC2.2), facts as counts; words are the screen's copy. */
const GLANCE: readonly GlanceRowOut[] = [
  {
    key: "people",
    tone: "ok",
    facts: { used: 46, total: 46, pending: 0, partners: 7, operations: 2 },
    href: "/settings/people",
  },
  {
    key: "offices_teams",
    tone: "ok",
    facts: { offices: 3, teams: 4, walls: 3 },
    href: "/settings/offices",
  },
  { key: "security", tone: "attention", facts: { open_incidents: 1, day: 4, of: 30 } },
  { key: "ai_policy", tone: "ok", facts: { version: 3 } },
  { key: "consents", tone: "attention", facts: { expiring: 2, within_days: 30, expired: 1 } },
  { key: "developer", tone: "ok", facts: { api_keys: 2, webhooks: 3, mcp_connections: 1 } },
  { key: "integrations", tone: "ok", facts: { connected: 9, errors: 0 } },
  { key: "portal", tone: "ok", facts: { published: 6, templates: 6, draft_changes: 1 } },
  { key: "quality", tone: "attention", facts: { objectives_at_risk: 2, open_findings: 5 } },
  {
    key: "monitoring",
    tone: "partial",
    facts: { inspections: 6, concluded: 3, in_progress: 1, planned: 2 },
  },
  { key: "audit_log", tone: "ok", facts: { retained_years: 7 } },
];

export const SETTINGS_AS_OF = "2026-09-14T09:24:00-05:00";

export function settingsOverview(viewer: SettingsViewer = "admin"): SettingsOverviewOut {
  const rows =
    viewer === "security"
      ? [
          ...GLANCE.filter((r) => r.key === "security"),
          ...GLANCE.filter((r) => r.key !== "security"),
        ]
      : [...GLANCE];
  return {
    firm_name: "Brightwater Hale LLP",
    sections: [
      { key: "profile", group: "firm", visible: true },
      { key: "defaults", group: "firm", visible: true },
      { key: "plan", group: "firm", visible: viewer !== "security" },
    ],
    at_a_glance: rows,
    as_of: SETTINGS_AS_OF,
  };
}

export type SectionKey = "profile" | "defaults" | "plan";
type Value = string | number | boolean | null;

/** ADM-01a's values. Keys later epics register (return approval policy, AJE thresholds, auto
 * mode, modules, renewal) are fixture-only so the form keeps parity (G-01 §2.1). */
export const SECTION_VALUES: Readonly<Record<SectionKey, Readonly<Record<string, Value>>>> = {
  profile: {
    legal_name: "Brightwater Hale LLP",
    display_name: "Brightwater Hale",
    time_zone: "America/Chicago",
    intake_mailbox: "docs@brightwaterhale.com",
    website: "brightwaterhale.com",
    seatless_staff_count: SEATLESS_STAFF,
  },
  plan: {
    seats: SEATS_TOTAL,
    billing_contact_user_id: stableId("user:grace-holloway"),
    modules: "tax,audit,cas,advisory",
    renewal_on: "2027-01-01",
  },
  defaults: {
    return_approval_policy: "BH-TAX-02",
    aje_threshold_policy: "BH AJE thresholds v2",
    auto_mode_new_audits: false,
    portal_secured_footer: false,
    week_starts_on: "monday",
  },
};
const READ_ONLY = new Set(["seats", "modules", "renewal_on"]);

export function settingsSection(
  section: SectionKey,
  viewer: SettingsViewer = "admin",
  values: Readonly<Record<string, Value>> = SECTION_VALUES[section],
  version = 1,
): SettingsSectionValuesOut | undefined {
  if (section === "plan" && viewer === "security") return undefined; // AC1.7: absent
  const admin = viewer === "admin";
  const out: SettingValueOut[] = Object.entries(values).map(([key, value]) => ({
    key,
    value,
    editable: admin && !READ_ONLY.has(key),
  }));
  return {
    section,
    values: out,
    version,
    read_only_reason: admin ? null : "firm_admin_only",
    allowed_actions: admin ? ["firm.manage_settings"] : [],
  };
}

/** Grace Holloway's user id, for the plan's billing contact. */
export const GRACE = userIdOf(seatOf("GH"));
export { SEATS };
