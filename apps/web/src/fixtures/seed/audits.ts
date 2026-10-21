// The 27 audits and assurance engagements of the E0 audit-core slice (blueprint 01 §9.7 "Audits &
// assurance (27)", A1 to A27) and the Feld household's TY2025 Form 1040 (the Feld 2025 Binder's
// engagement), shaped as C1 freezes them: EngagementOut with its G1 to G3 gates, one assurance
// WorkItemOut per attest engagement, the registry's lifecycle words (C2, DEC-122).

import type {
  EngagementOut,
  EngagementStatus,
  EngagementSummaryOut,
  GateOut,
  WorkItemOut,
} from "@abacus/api-client";
import { daysBefore, onDate } from "./clock";
import { type SeedClient, entityIdOf } from "./clients";
import { Rng, stableId } from "./prng";
import { SEATS, slugOf } from "./people";

export type EngagementType = EngagementOut["type"];
type TeamMember = EngagementOut["team"][number];
/** audit_engagement codes in docs/product/status-vocabulary.yaml (an assurance item's phase). */
export type AuditPhase = "planning" | "fieldwork" | "in_review" | "ready_to_release" | "released";

interface AuditRow {
  n: number;
  /** The client's name as the clients module spells it. */
  client: string;
  /** The entity the engagement is for, when it is not the client itself. */
  entity?: string;
  name: string;
  type: EngagementType;
  start: string;
  end: string;
  phase: AuditPhase;
  /** Engagement partner (initials). */
  ep: string;
  status: EngagementStatus;
  /** The letter is out but not fully signed: G3 is not met and the engagement stays Accepted. */
  letterOut?: boolean;
  /** An exact creation date when the handoff gives one; otherwise the date is generated. */
  created?: string;
  dueOn?: string;
}

const CAL_2025 = ["2025-01-01", "2025-12-31"] as const;
const FYE_JUN_2026 = ["2025-07-01", "2026-06-30"] as const;

const EBP = (
  n: number,
  client: string,
  phase: AuditPhase,
  ep: string,
  extra: Partial<AuditRow> = {},
): AuditRow => ({
  n,
  client,
  name: "PY2025 EBP Audit",
  type: "ebp_audit",
  start: CAL_2025[0],
  end: CAL_2025[1],
  phase,
  ep,
  status: phase === "released" ? "delivered" : "active",
  ...extra,
});

const FS = (
  n: number,
  client: string,
  phase: AuditPhase,
  ep: string,
  period: readonly [string, string],
  name: string,
  extra: Partial<AuditRow> = {},
): AuditRow => ({
  n,
  client,
  name,
  type: "fs_audit",
  start: period[0],
  end: period[1],
  phase,
  ep,
  status: phase === "released" ? "delivered" : "active",
  ...extra,
});

const REVIEW = (
  n: number,
  client: string,
  phase: AuditPhase,
  ep: string,
  extra: Partial<AuditRow> = {},
): AuditRow => ({
  n,
  client,
  name: "FY2026 SSARS Review",
  type: "review",
  start: FYE_JUN_2026[0],
  end: FYE_JUN_2026[1],
  phase,
  ep,
  status: "active",
  ...extra,
});

// Tiles at E0: Planning 7 · Fieldwork 9 · In review 6 · Ready to release 2 · Released 3, and
// EBP 14 · FS audit 6 · Review 4 · Compilation and preparation 3. Released maps to Delivered, and
// to Archived once the archive lock is on (A4 and A20, the two Archived engagements of ENG-01).
const ROWS: readonly AuditRow[] = [
  EBP(1, "Northwind Robotics, Inc.", "planning", "MO", {
    entity: "Northwind Robotics 401(k) Plan",
    created: "2026-05-28",
    dueOn: "2026-10-09",
  }),
  FS(2, "Granite Peak Outdoor Supply, Inc.", "planning", "MO", FYE_JUN_2026, "FY2026 FS Audit", {
    status: "accepted",
    letterOut: true,
    created: "2026-08-31",
  }),
  REVIEW(3, "Lakeshore Literacy Alliance", "fieldwork", "CM", {
    dueOn: "2026-10-30",
    created: "2026-07-20",
  }),
  {
    n: 4,
    client: "Juniper & Oak Interiors, LLC",
    name: "FY2025 Preparation (AR-C 70)",
    type: "preparation",
    start: CAL_2025[0],
    end: CAL_2025[1],
    phase: "released",
    ep: "PR",
    status: "archived",
    created: "2026-01-12",
  },
  EBP(5, "Cobalt Ridge Manufacturing 401(k) Plan", "ready_to_release", "TW"),
  EBP(6, "Halden Health 403(b) Plan", "ready_to_release", "CM"),
  EBP(7, "Fairhaven Foods 401(k) Plan", "planning", "MO", {
    status: "accepted",
    letterOut: true,
    created: "2026-09-08",
  }),
  EBP(8, "Sterling Freight 401(k) Plan", "fieldwork", "TW"),
  EBP(9, "Westbrook Engineering 401(k) Plan", "fieldwork", "CM"),
  EBP(10, "Arbor Senior Living 401(k) Plan", "fieldwork", "MO"),
  EBP(11, "Keel & Compass Marine 401(k) Plan", "in_review", "TW"),
  EBP(12, "Redtail Construction 401(k) Plan", "in_review", "CM"),
  EBP(13, "Clearwater Credit Union 401(k) Plan", "fieldwork", "MO"),
  EBP(14, "Granite Peak Outdoor Supply, Inc.", "fieldwork", "MO", {
    entity: "Granite Peak Outdoor Supply 401(k) Plan",
  }),
  EBP(15, "Hearthstone Hospitality 401(k) Plan", "in_review", "TW"),
  EBP(16, "Bayside Electric Cooperative 401(k) Plan", "released", "CM"),
  EBP(17, "Tamarack Health System 403(b) Plan", "planning", "CM"),
  FS(18, "Larimer Cooperative Grocery", "planning", "TW", FYE_JUN_2026, "FY2026 FS Audit"),
  FS(19, "Sable Creek Homeowners Association", "fieldwork", "CM", FYE_JUN_2026, "FY2026 FS Audit"),
  FS(20, "Meridian Tool & Die, Inc.", "released", "MO", CAL_2025, "FY2025 FS Audit", {
    status: "archived",
  }),
  FS(21, "Halcyon Foods Distribution, Inc.", "planning", "TW", FYE_JUN_2026, "FY2026 FS Audit"),
  FS(
    22,
    "Oakline Software, Inc.",
    "in_review",
    "CM",
    ["2025-04-01", "2026-03-31"],
    "FY2026 FS Audit",
  ),
  REVIEW(23, "Riverbend Community Theater", "planning", "CM"),
  REVIEW(24, "Hillcrest Montessori School", "fieldwork", "TW"),
  REVIEW(25, "Wildflower Land Trust", "in_review", "CM"),
  {
    n: 26,
    client: "Fenwick Family Foundation",
    name: "FY2025 Compilation (AR-C 80)",
    type: "compilation",
    start: CAL_2025[0],
    end: CAL_2025[1],
    phase: "fieldwork",
    ep: "PR",
    status: "active",
  },
  {
    n: 27,
    client: "Kettle & Kiln Pottery, LLC",
    name: "FY2025 Preparation (AR-C 70)",
    type: "preparation",
    start: CAL_2025[0],
    end: CAL_2025[1],
    phase: "in_review",
    ep: "PR",
    status: "active",
  },
];

const ATTEST = new Set<EngagementType>(["fs_audit", "ebp_audit", "review"]);

// Team pools. Northwind's five are named in the handoff (AUD-03 rail: MO · TW · HL · MD · AC).
const AUDIT_MANAGERS = ["LK", "OH"];
const AUDIT_SENIORS = ["CD", "JB", "SB"];
const AUDIT_STAFF = ["AW", "FN", "KR", "CH", "HP"];
const CAS_SENIORS = ["EW", "RF"];
const CAS_STAFF = ["IV", "EG"];

function member(initials: string, role: TeamMember["role"]): TeamMember {
  const seat = SEATS.find((s) => s.initials === initials);
  if (seat === undefined) throw new Error(`no seat ${initials}`);
  return { user_id: stableId(`user:${slugOf(seat.name)}`), display_name: seat.name, role };
}

function teamFor(row: AuditRow): TeamMember[] {
  if (row.n === 1) {
    return [
      member("MO", "engagement_partner"),
      member("HL", "manager"),
      member("MD", "senior"),
      member("AC", "staff"),
      member("TW", "reviewer"),
    ];
  }
  const rng = new Rng(`team:${String(row.n)}`);
  const cas = row.ep === "PR";
  const team = [member(row.ep, "engagement_partner")];
  if (!cas) team.push(member(rng.pick(AUDIT_MANAGERS), "manager"));
  team.push(member(rng.pick(cas ? CAS_SENIORS : AUDIT_SENIORS), "senior"));
  team.push(member(rng.pick(cas ? CAS_STAFF : AUDIT_STAFF), "staff"));
  if (row.n === 22) team.push(member("TW", "reviewer")); // A22: "EQR TW"
  return team;
}

/** The G1 to G3 gates the type requires (gate_policy.py), met unless the letter is still out. */
function gatesFor(row: AuditRow): GateOut[] {
  const gates: GateOut[] = [];
  const wanted = ATTEST.has(row.type) ? ["G1", "G2", "G3"] : ["G1", "G3"];
  for (const gate of wanted) {
    const blocked = gate === "G3" && row.letterOut === true;
    gates.push({
      gate: gate as "G1" | "G2" | "G3",
      met: !blocked,
      blockers: blocked ? ["engagement_letter"] : [],
    });
  }
  return gates;
}

function createdAt(row: AuditRow): string {
  if (row.created !== undefined) return onDate(row.created);
  const rng = new Rng(`created:${String(row.n)}`);
  const late = row.phase === "released" || row.phase === "ready_to_release";
  return daysBefore(late ? rng.int(120, 300) : rng.int(30, 240));
}

export interface Engagements {
  engagements: EngagementOut[];
  workItems: Record<string, WorkItemOut[]>;
  /** engagement id by label: "A1" to "A27" and "feld". */
  ids: Record<string, string>;
}

/** The Feld household's TY2025 Form 1040: its binder's engagement. The tax_return item is a shell. */
function feld(clients: ReadonlyMap<string, SeedClient>): [EngagementOut, WorkItemOut[]] {
  const client = clients.get("Jonah & Claire Feld");
  if (client === undefined) throw new Error("no Feld client");
  const id = stableId("engagement:feld");
  const engagement: EngagementOut = {
    id,
    name: "TY2025 Form 1040",
    type: "tax_compliance",
    status: "active",
    service_line: "tax",
    client_id: stableId(`client:${client.slug}`),
    client_name: client.name,
    client_entity_id: entityIdOf(client.slug, client.name),
    client_entity_name: client.name,
    fiscal_period_start: "2025-01-01",
    fiscal_period_end: "2025-12-31",
    created_at: onDate("2026-02-02"),
    team: [
      member("DR", "engagement_partner"),
      member("SI", "manager"),
      member("OB", "senior"),
      member("KO", "staff"),
    ],
    gates: [
      { gate: "G1", met: true, blockers: [] },
      { gate: "G3", met: true, blockers: [] },
    ],
  };
  const item: WorkItemOut = {
    id: stableId("work-item:feld"),
    kind: "tax_return",
    name: "TY2025 Form 1040",
    status: "active",
    period_start: "2025-01-01",
    period_end: "2025-12-31",
    due_on: "2026-10-15",
    phase: null,
  };
  return [engagement, [item]];
}

export function buildEngagements(clients: readonly SeedClient[]): Engagements {
  const byName = new Map(clients.map((c) => [c.name, c]));
  const engagements: EngagementOut[] = [];
  const workItems: Record<string, WorkItemOut[]> = {};
  const ids: Record<string, string> = {};
  for (const row of ROWS) {
    const client = byName.get(row.client);
    if (client === undefined) continue; // a holdout left the client (and so its engagement) out
    const entity = row.entity ?? client.name;
    const id = stableId(`engagement:A${String(row.n)}`);
    ids[`A${String(row.n)}`] = id;
    engagements.push({
      id,
      name: row.name,
      type: row.type,
      status: row.status,
      service_line: "audit",
      client_id: stableId(`client:${client.slug}`),
      client_name: client.name,
      client_entity_id: entityIdOf(client.slug, entity),
      client_entity_name: entity,
      fiscal_period_start: row.start,
      fiscal_period_end: row.end,
      created_at: createdAt(row),
      team: teamFor(row),
      gates: gatesFor(row),
    });
    workItems[id] = [
      {
        id: stableId(`work-item:A${String(row.n)}`),
        kind: "assurance",
        name: row.name,
        status: row.status === "archived" ? "archived" : "active",
        period_start: row.start,
        period_end: row.end,
        due_on: row.dueOn ?? null,
        phase: row.phase,
      },
    ];
  }
  const [feldEngagement, feldItems] = feld(byName);
  engagements.push(feldEngagement);
  workItems[feldEngagement.id] = feldItems;
  ids.feld = feldEngagement.id;
  return { engagements, workItems, ids };
}

/** The list projection: an engagement without its team and gates (EngagementSummaryOut). */
export function summaryOf(engagement: EngagementOut): EngagementSummaryOut {
  return {
    id: engagement.id,
    name: engagement.name,
    type: engagement.type,
    status: engagement.status,
    service_line: engagement.service_line,
    client_id: engagement.client_id,
    client_name: engagement.client_name,
    client_entity_id: engagement.client_entity_id,
    client_entity_name: engagement.client_entity_name,
    fiscal_period_start: engagement.fiscal_period_start,
    fiscal_period_end: engagement.fiscal_period_end,
    created_at: engagement.created_at,
  };
}
