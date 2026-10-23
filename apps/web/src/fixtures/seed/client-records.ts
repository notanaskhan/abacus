// CLI-02's client records (P-07-T19; docs/screens/CLI-02.md): the record (`ClientRecordOut`), the
// per-kind overview (`ClientOverviewOut`) and the relationship list for the five clients its
// artboards open on, typed with the generated client. Names, figures and dates are verbatim from
// the handoff (spec.md a, b, c, e; revision.md f) and the shared context block; nothing is ported
// from kit sample data.
//
//   a, a2  Ridgeline Property Partners, LP (business): K-1s, waiting on client, key dates
//   b      Jonah & Claire Feld (household): one 1040 holding a draft Ridgeline K-1
//   c      Northwind Robotics, Inc. (plan sponsor, attest by DEC-128): the PY2025 plan audit
//   e      Copperleaf Coffee Roasters, Inc. on its onboarding day: no engagements, no sections
//   f      Granite Peak Outdoor Supply, Inc. with the `insights` entitlement: responsiveness
//
// The overview's sections are the registered providers' (docs/contracts/clients.md §1): the live
// ones (`entities`, `engagements`, `key_dates`, `contacts`) keep their codes and item keys; the
// rest are what the providers still to land will register (`stats`, `profile`, `portal`,
// `links`, `work_items`, `k1_packages`, `waiting_on_client`, `activity`; `responsiveness` from
// I-03). Each is the contract's generic item, never a field the contract lacks; what the item
// cannot carry yet is a deviation in the screen contract, not a field here.
//
// Ridgeline's accounting method (spec a) is left out: its value is T-01's provider's, and the
// handoff's word for the method is the one the brand lint bans in source (docs/screens/CLI-02.md,
// Open gaps).
//
// An "x of y" stat is two items: `<key>` holds x and `<key>.of` holds y (no item has a
// denominator). Money and counts are decimal strings (ADR-050); sums are computed in code.

import type {
  ClientEngagementBriefOut,
  ClientEntityBriefOut,
  ClientOverviewItemOut,
  ClientOverviewOut,
  ClientOverviewSectionOut,
  ClientRecordOut,
  ClientRelationshipOut,
} from "@abacus/api-client";
import type { Seed } from ".";
import { entityIdOf, slugOfClient } from "./clients";
import { slugOf } from "./people";
import { stableId } from "./prng";
import { officeIdOf } from "./shell";

export const RIDGELINE = "Ridgeline Property Partners, LP";
export const FELD = "Jonah & Claire Feld";
export const NORTHWIND = "Northwind Robotics, Inc.";
export const COPPERLEAF = "Copperleaf Coffee Roasters, Inc.";
export const GRANITE_PEAK = "Granite Peak Outdoor Supply, Inc.";

/** The clients CLI-02's artboards open on. */
export const RECORD_CLIENTS = [RIDGELINE, FELD, NORTHWIND, COPPERLEAF, GRANITE_PEAK] as const;
export type RecordClient = (typeof RECORD_CLIENTS)[number];

export interface ClientRecordFixture {
  record: ClientRecordOut;
  overview: ClientOverviewOut;
  relationships: ClientRelationshipOut[];
  /** The plain TIN a reveal returns, by entity id: the seed's synthetic value (blueprint §9). */
  reveal: Record<string, string>;
}

export function clientIdOf(name: string): string {
  return stableId(`client:${slugOfClient(name)}`);
}

export function userIdOf(name: string): string {
  return stableId(`user:${slugOf(name)}`);
}

function engagementIdOf(client: string, name: string): string {
  return stableId(`engagement:${slugOfClient(client)}:${slugOfClient(name)}`);
}

function entity(
  client: string,
  name: string,
  facts: Omit<ClientEntityBriefOut, "id" | "name">,
): ClientEntityBriefOut {
  return { id: entityIdOf(slugOfClient(client), name), name, ...facts };
}

function section(
  code: string,
  kind: ClientOverviewSectionOut["kind"],
  read_action: string,
  items: ClientOverviewItemOut[],
  total?: number,
): ClientOverviewSectionOut {
  return { code, kind, read_action, items, ...(total === undefined ? {} : { total }) };
}

const CLIENT_READ = "client.read";
const ENGAGEMENT_READ = "engagement.read_metadata";
/** The work-item providers' read action (T-02, T-05, T-09): content, not metadata. */
const CONTENT_READ = "engagement.read";

/** Every action Daniel Reyes holds on a client record he is the relationship partner of. */
const PARTNER_ACTIONS = ["client.read", "client.update", "tin.reveal"];

// ---- a: Ridgeline -------------------------------------------------------------------------------

function ridgeline(): ClientRecordFixture {
  const id = clientIdOf(RIDGELINE);
  const lp = entity(RIDGELINE, RIDGELINE, {
    entity_type: "partnership",
    fye_month_day: "12-31",
    state_of_formation: null,
    plan_number: null,
    tin: { kind: "ein", presence: "on_file", last4: "0287" },
  });
  const tax = engagementIdOf(RIDGELINE, "2025 Form 1065");
  const advisory = engagementIdOf(RIDGELINE, "Ridgeline cost segregation & §754 analysis");
  const engagements: ClientEngagementBriefOut[] = [
    { id: tax, name: "2025 Form 1065", service_line: "tax", status: "active" },
    {
      id: advisory,
      name: "Ridgeline cost segregation & §754 analysis",
      service_line: "advisory",
      status: "accepted",
    },
  ];
  const feldReturn = stableId("return:jonah-and-claire-feld:2025-form-1040");
  const shahReturn = stableId("return:meera-shah:2025-form-1040");
  const k1 = (text: string, figure: string, feeds: string | null): ClientOverviewItemOut => ({
    key: "k1_package",
    text,
    figure,
    pill_object: "k1_package",
    pill_code: "draft",
    // Released together Sep 15, 2026, 10:30 AM (spec acceptance).
    at: "2026-09-15T10:30:00-05:00",
    ref: feeds === null ? null : { type: "return", id: feeds },
  });
  const record: ClientRecordOut = {
    id,
    name: RIDGELINE,
    descriptor: "Real estate partnership · Form 1065",
    kind: "business",
    status: "active",
    is_attest_client: false,
    risk_tier: "moderate",
    primary_office_id: officeIdOf("New York"),
    office_name: "New York",
    relationship_partner_id: userIdOf("Daniel Reyes"),
    manager_user_ids: [userIdOf("Samuel Ito")],
    preparer_user_ids: [userIdOf("Olivia Brandt")],
    portal_status: "active",
    entities: [lp],
    active_engagements: engagements,
    tab_counts: { engagements: 2, relationships: 6, contacts: 5, messages: 1 },
    version: 7,
    allowed_actions: PARTNER_ACTIONS,
  };
  const overview: ClientOverviewOut = {
    client_id: id,
    profile: "business",
    sections: [
      section("stats", "stats", CONTENT_READ, [
        { key: "open_issues", figure: "11", text: "Open issues on the 2025 return" },
        { key: "waiting_on_client", figure: "5", text: "Waiting on client" },
        { key: "k1_shared", figure: "2", text: "K-1s shared as drafts" },
        { key: "k1_shared.of", figure: "5" },
        { key: "days_to_due", on: "2026-09-15", text: "To extended due date (Sep 15)" },
      ]),
      section("portal", "details", CLIENT_READ, [
        { key: "contact", text: "Owen Calder" },
        { key: "email", text: "owen.calder@ridgelinepp.com" },
        { key: "requests", figure: "5" },
      ]),
      section("links", "details", CLIENT_READ, [
        {
          key: "binder",
          text: "2025 Binder",
          ref: { type: "binder", id: stableId("binder:ridgeline:2025") },
        },
      ]),
      section(
        "engagements",
        "table",
        ENGAGEMENT_READ,
        [
          {
            key: "engagement",
            text: "2025 Form 1065",
            on: "2025-12-31",
            pill_object: "engagement",
            pill_code: "active",
            ref: { type: "engagement", id: tax },
          },
          {
            key: "engagement",
            text: "Ridgeline cost segregation & §754 analysis",
            on: "2026-12-31",
            pill_object: "engagement",
            pill_code: "accepted",
            ref: { type: "engagement", id: advisory },
          },
        ],
        2,
      ),
      section("work_items", "table", CONTENT_READ, [
        {
          key: "return",
          text: "2025 Form 1065",
          figure: "11",
          pill_object: "return",
          pill_code: "in_review",
          ref: { type: "return", id: stableId("return:ridgeline:2025-form-1065") },
        },
        {
          key: "project",
          text: "Ridgeline cost segregation & §754 analysis",
          pill_object: "project",
          pill_code: "scoping",
          ref: { type: "project", id: stableId("project:ridgeline:cost-segregation") },
        },
      ]),
      section(
        "k1_packages",
        "table",
        CONTENT_READ,
        [
          k1("Ridgeline GP LLC", "24632", null),
          k1("Meera Shah", "468008", shahReturn),
          k1("Pell Street Ventures LLC", "400270", null),
          k1("Pell Street II LLC (7/1–12/31)", "30790", null),
          k1("Jonah Feld", "307900", feldReturn),
        ],
        5,
      ),
      section(
        "waiting_on_client",
        "table",
        CONTENT_READ,
        [
          {
            key: "issue",
            text: "§754 election: partners' decision and support for Pell Street II's $360,000 purchase price",
            at: "2026-09-11T10:00:00-05:00",
          },
          {
            key: "issue",
            text: "December real estate tax installment: county bill supporting the 18,500 accrual",
            at: "2026-09-10T10:00:00-05:00",
          },
        ],
        5,
      ),
      section("key_dates", "key_dates", CLIENT_READ, [
        { key: "due", on: "2026-09-15", text: "Form 1065 extended due date" },
        { key: "due", on: "2026-09-24", text: "Cost segregation engagement letter due back" },
        { key: "due", on: "2026-10-15", text: "Feld and Shah 1040s (depend on Ridgeline K-1s)" },
        {
          key: "due",
          on: "2027-09-15",
          text: "Last day for a late §754 election under Reg. §301.9100-2 (if not elected with the return)",
        },
      ]),
      section("activity", "activity", CLIENT_READ, [
        {
          key: "letter.sent",
          at: "2026-09-14T08:40:00-05:00",
          text: 'Daniel Reyes sent the engagement letter "Ridgeline cost segregation & §754 analysis" to Owen Calder',
        },
        {
          key: "allocation.approved",
          at: "2026-09-12T11:00:00-05:00",
          text: "Samuel Ito approved the Allocation Structure (straight percentage; §706(d) interim closing, monthly convention)",
        },
        {
          key: "memo.drafted",
          at: "2026-09-11T11:00:00-05:00",
          text: "Accrued Agent drafted the preparer memo · run by Olivia Brandt",
        },
        {
          key: "k1.shared",
          at: "2026-09-10T11:00:00-05:00",
          text: "Olivia Brandt shared draft K-1s with the Feld and Shah 1040s",
        },
        { key: "form_7004.filed", at: "2026-03-12T11:00:00-05:00", text: "Form 7004 filed" },
      ]),
    ],
  };
  const edge = (
    to: string,
    kind: ClientRelationshipOut["kind"],
    percent: string | null,
  ): ClientRelationshipOut => ({
    id: stableId(`relationship:ridgeline:${slugOfClient(to)}`),
    kind,
    from_entity_id: entityIdOf(slugOfClient(to), to),
    from_entity_name: to,
    to_entity_id: lp.id,
    to_entity_name: RIDGELINE,
    to_client_id: id,
    percent,
  });
  // The five K-1 recipients and the Pell Street II purchase (spec a: "6 parties").
  const relationships = [
    edge("Ridgeline GP LLC", "gp_of", null),
    edge("Meera Shah", "lp_of", null),
    edge("Pell Street Ventures LLC", "lp_of", null),
    edge("Pell Street II LLC", "lp_of", null),
    edge("Jonah Feld", "lp_of", null),
    edge("Owen Calder", "owner_of", null),
  ];
  return { record, overview, relationships, reveal: { [lp.id]: "00-0000287" } };
}

// ---- b: Feld -------------------------------------------------------------------------------------

function feld(): ClientRecordFixture {
  const id = clientIdOf(FELD);
  const claire = entity(FELD, "Claire Feld", {
    entity_type: "individual",
    tin: { kind: "ssn", presence: "on_file", last4: "2208" },
  });
  const household = entity(FELD, FELD, { entity_type: "household_mfj", fye_month_day: "12-31" });
  const ret = engagementIdOf(FELD, "2025 Form 1040");
  const record: ClientRecordOut = {
    id,
    name: FELD,
    descriptor: "MFJ · Form 1040 · Brooklyn, NY",
    kind: "household",
    status: "active",
    is_attest_client: false,
    risk_tier: null,
    primary_office_id: officeIdOf("New York"),
    office_name: "New York",
    relationship_partner_id: userIdOf("Daniel Reyes"),
    manager_user_ids: [userIdOf("Samuel Ito")],
    preparer_user_ids: [userIdOf("Kevin Osei")],
    portal_status: "active",
    entities: [household, claire],
    active_engagements: [
      { id: ret, name: "2025 Form 1040", service_line: "tax", status: "active" },
    ],
    tab_counts: { engagements: 1, relationships: 2, contacts: 2, messages: null },
    version: 4,
    allowed_actions: PARTNER_ACTIONS,
  };
  const overview: ClientOverviewOut = {
    client_id: id,
    profile: "household",
    sections: [
      section("stats", "stats", CONTENT_READ, [
        { key: "open_issues", figure: "4", text: "Open issues" },
        { key: "requests_open", figure: "2", text: "Requests open" },
        { key: "documents_in_review", figure: "37", text: "Documents in review" },
        { key: "days_to_due", on: "2026-10-15", text: "To Oct 15" },
      ]),
      section("profile", "details", CLIENT_READ, [
        { key: "filing_status", text: "Married filing jointly" },
        { key: "resident", text: "New York (incl. NYC)" },
        { key: "consents_7216", text: "Use · AI disclosure (2 consents)" },
      ]),
      section(
        "engagements",
        "table",
        ENGAGEMENT_READ,
        [
          {
            key: "engagement",
            text: "2025 Form 1040",
            on: "2025-12-31",
            pill_object: "engagement",
            pill_code: "active",
            ref: { type: "engagement", id: ret },
          },
        ],
        1,
      ),
      section("work_items", "table", CONTENT_READ, [
        {
          key: "return",
          text: "2025 Form 1040",
          pill_object: "return",
          pill_code: "in_review",
          ref: { type: "return", id: stableId("return:jonah-and-claire-feld:2025-form-1040") },
        },
      ]),
      section(
        "k1_packages",
        "table",
        CONTENT_READ,
        [
          {
            key: "k1_received",
            text: RIDGELINE,
            figure: "307900",
            pill_object: "k1_package",
            pill_code: "draft",
            ref: { type: "client", id: clientIdOf(RIDGELINE) },
          },
        ],
        1,
      ),
    ],
  };
  const relationships: ClientRelationshipOut[] = [
    {
      id: stableId("relationship:feld:spouse"),
      kind: "spouse",
      from_entity_id: entityIdOf(slugOfClient(FELD), "Jonah Feld"),
      from_entity_name: "Jonah Feld",
      to_entity_id: claire.id,
      to_entity_name: "Claire Feld",
      to_client_id: id,
    },
    {
      id: stableId("relationship:ridgeline:jonah-feld"),
      kind: "lp_of",
      from_entity_id: entityIdOf(slugOfClient(FELD), "Jonah Feld"),
      from_entity_name: "Jonah Feld",
      to_entity_id: entityIdOf(slugOfClient(RIDGELINE), RIDGELINE),
      to_entity_name: RIDGELINE,
      to_client_id: clientIdOf(RIDGELINE),
    },
  ];
  return { record, overview, relationships, reveal: { [claire.id]: "000-00-2208" } };
}

// ---- c: Northwind -------------------------------------------------------------------------------

function northwind(seed: Seed): ClientRecordFixture {
  const id = clientIdOf(NORTHWIND);
  const plan = entity(NORTHWIND, "Northwind Robotics 401(k) Plan", {
    entity_type: "ebp_plan",
    plan_number: "001",
    fye_month_day: "12-31",
  });
  const sponsor = entity(NORTHWIND, NORTHWIND, { entity_type: "c_corp", fye_month_day: "12-31" });
  const audit = seed.engagementIds.A1 ?? engagementIdOf(NORTHWIND, "PY2025 EBP Audit");
  // PBC 11 of 24 (CLI-01 Northwind 13 = 24 − 11), counted from the seed's own request list.
  const pbc = seed.requestItems[audit] ?? [];
  const received = pbc.filter((r) => r.status === "received").length;
  const record: ClientRecordOut = {
    id,
    name: NORTHWIND,
    descriptor: "Plan sponsor · Northwind Robotics 401(k) Plan",
    kind: "plan_sponsor",
    status: "active",
    is_attest_client: true,
    risk_tier: null,
    primary_office_id: officeIdOf("Chicago"),
    office_name: "Chicago",
    relationship_partner_id: userIdOf("Margaret Okonkwo"),
    manager_user_ids: [userIdOf("Hannah Leclerc")],
    preparer_user_ids: [userIdOf("Marcus Delaney")],
    portal_status: "active",
    entities: [sponsor, plan],
    active_engagements: [
      { id: audit, name: "PY2025 EBP Audit", service_line: "audit", status: "active" },
    ],
    tab_counts: { engagements: 1, relationships: 1, contacts: 3, messages: null },
    version: 3,
    allowed_actions: ["client.read"],
  };
  const overview: ClientOverviewOut = {
    client_id: id,
    profile: "plan_sponsor",
    sections: [
      section("stats", "stats", CONTENT_READ, [
        { key: "pbc_received", figure: String(received), text: "PBC received" },
        { key: "pbc_received.of", figure: String(pbc.length) },
        {
          key: "run",
          pill_object: "audit_engagement",
          pill_code: "processing",
          text: "Run badge",
        },
        { key: "report_target", on: "2026-10-09", text: "Report target" },
        { key: "form_5500_due", on: "2026-10-15", text: "Form 5500 due (5558)" },
      ]),
      section("profile", "details", CLIENT_READ, [
        {
          key: "plan",
          text: "Northwind Robotics 401(k) Plan · PN 001 · §103(a)(3)(C)",
          ref: { type: "client_entity", id: plan.id },
        },
        { key: "ske_designee", text: "Dana Kowalski" },
        { key: "independence", text: "4 of 5 confirmed", ref: { type: "engagement", id: audit } },
      ]),
      section(
        "engagements",
        "table",
        ENGAGEMENT_READ,
        [
          {
            key: "engagement",
            text: "PY2025 EBP Audit",
            on: "2025-12-31",
            pill_object: "engagement",
            pill_code: "active",
            ref: { type: "engagement", id: audit },
          },
        ],
        1,
      ),
    ],
  };
  const relationships: ClientRelationshipOut[] = [
    {
      id: stableId("relationship:northwind:sponsor"),
      kind: "sponsor_of",
      from_entity_id: sponsor.id,
      from_entity_name: NORTHWIND,
      to_entity_id: plan.id,
      to_entity_name: plan.name,
      to_client_id: id,
    },
  ];
  return { record, overview, relationships, reveal: {} };
}

// ---- e: Copperleaf ------------------------------------------------------------------------------

function copperleaf(): ClientRecordFixture {
  const id = clientIdOf(COPPERLEAF);
  const corp = entity(COPPERLEAF, COPPERLEAF, {
    entity_type: "s_corp",
    fye_month_day: "12-31",
    tin: { kind: "ein", presence: "applied_for", last4: null },
  });
  const record: ClientRecordOut = {
    id,
    name: COPPERLEAF,
    descriptor: "Denver, CO · café + online store",
    kind: "business",
    status: "active",
    is_attest_client: false,
    risk_tier: null,
    primary_office_id: officeIdOf("Denver"),
    office_name: "Denver",
    relationship_partner_id: userIdOf("Priya Raman"),
    manager_user_ids: [],
    preparer_user_ids: [],
    portal_status: "not_invited",
    entities: [corp],
    active_engagements: [],
    tab_counts: { engagements: 0, relationships: 0, contacts: 0, messages: null },
    version: 1,
    allowed_actions: PARTNER_ACTIONS,
  };
  const overview: ClientOverviewOut = { client_id: id, profile: "business", sections: [] };
  return { record, overview, relationships: [], reveal: {} };
}

// ---- f: Granite Peak ----------------------------------------------------------------------------

function granitePeak(seed: Seed): ClientRecordFixture {
  const id = clientIdOf(GRANITE_PEAK);
  const corp = entity(GRANITE_PEAK, GRANITE_PEAK, {
    entity_type: "c_corp",
    fye_month_day: "06-30",
  });
  const audit =
    seed.engagementIds.A2 ?? engagementIdOf(GRANITE_PEAK, "FY2026 Financial Statement Audit");
  const record: ClientRecordOut = {
    id,
    name: GRANITE_PEAK,
    descriptor: "C corp · Denver",
    kind: "business",
    status: "active",
    is_attest_client: true,
    risk_tier: null,
    primary_office_id: officeIdOf("Denver"),
    office_name: "Denver",
    relationship_partner_id: userIdOf("Margaret Okonkwo"),
    manager_user_ids: [],
    preparer_user_ids: [],
    portal_status: "active",
    entities: [corp],
    active_engagements: [
      {
        id: audit,
        name: "FY2026 Financial Statement Audit",
        service_line: "audit",
        status: "active",
      },
    ],
    tab_counts: { engagements: 1, relationships: 0, contacts: 2, messages: null },
    version: 2,
    allowed_actions: ["client.read"],
  };
  const overview: ClientOverviewOut = {
    client_id: id,
    profile: "business",
    sections: [
      section(
        "engagements",
        "table",
        ENGAGEMENT_READ,
        [
          {
            key: "engagement",
            text: "FY2026 Financial Statement Audit",
            on: "2026-06-30",
            pill_object: "engagement",
            pill_code: "active",
            ref: { type: "engagement", id: audit },
          },
        ],
        1,
      ),
      // I-03's INS-05 read model behind the `insights` entitlement (revision R2 f): the client's
      // season-to-date on-time rate against the firm's, and its overdue requests.
      section("responsiveness", "stats", "insights.read", [
        { key: "on_time_rate", figure: "48" },
        { key: "firm_rate", figure: "63" },
        { key: "overdue_now", figure: "3", ref: { type: "engagement", id: audit } },
      ]),
    ],
  };
  return { record, overview, relationships: [], reveal: {} };
}

/** The five records, by client name. */
export function clientRecords(seed: Seed): Record<RecordClient, ClientRecordFixture> {
  return {
    [RIDGELINE]: ridgeline(),
    [FELD]: feld(),
    [NORTHWIND]: northwind(seed),
    [COPPERLEAF]: copperleaf(),
    [GRANITE_PEAK]: granitePeak(seed),
  };
}
