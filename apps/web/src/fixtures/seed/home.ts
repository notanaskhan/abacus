// HOME-01's slice of the Brightwater Hale E0 seed (I-01-T05; docs/screens/HOME-01.md, Rows and
// Figures). Every string and number is the handoff's (HOME-01 spec, revision R2 and the TPL-11
// frames for the spec-only role states b–e); nothing is invented. Typed against the generated
// client: `HomeOut` (the home half) and `HumanGateOut` (the gate half), so the one count source is
// computed from these rows by the handler, never stored beside them.
//
// Footings (proven in `home.foot.test.ts`): tax tiles 17 + 15 + 11 + 7 = 50 of 79 open; audits
// 7 + 9 + 6 + 2 + 3 = 27; closes 11 of 22; notices 9 with 2 New; Daniel 11 = 3 + 6 + 2; Margaret
// 4 = 2 + 2; Samuel 6 = 0 + 4 + 2; Kevin "My work 4"; Grace 2.

import type { HomeOut, HomeTileOut, HumanGateOut } from "@abacus/api-client";
import { slugOfClient } from "./clients";
import { DEMO_INSTANT } from "./clock";
import type { OfficeName } from "./people";
import { stableId } from "./prng";
import { officeIdOf } from "./shell";

/** HOME-01 h and i stand at 12:40 PM CT (the artboards' "Rendered" time). */
export const HOME_AFTERNOON = "2026-09-14T12:40:00-05:00";
export const HOME_TODAY = "2026-09-14";

export type HomePersona =
  | "daniel-reyes"
  | "margaret-okonkwo"
  | "samuel-ito"
  | "kevin-osei"
  | "grace-holloway"
  | "hannah-leclerc"
  | "marcus-delaney"
  | "lena-park";

const userId = (slug: string): string => stableId(`user:${slug}`);
const clientId = (name: string): string => stableId(`client:${slugOfClient(name)}`);

// The clients these rows name, with the office the seed files each under (seed/clients.ts).
const CLIENT_OFFICE: Readonly<Record<string, OfficeName>> = {
  "Ridgeline Property Partners, LP": "New York",
  "Marcus & Dana Whitley": "Denver",
  "Estate of Walter Thornbury": "Chicago",
  "Harborview Dental Properties, LP": "New York",
  "Northwind Robotics, Inc.": "Chicago",
  "Granite Peak Outdoor Supply, Inc.": "Denver",
  "Fairhaven Foods 401(k) Plan": "Chicago",
  "Jonah & Claire Feld": "New York",
  "Calloway Family Trust": "Chicago",
  "Summit Plan Administrators": "Chicago",
};

type Kind = HumanGateOut["kind"];
const BAND_OF: Readonly<Record<Kind, HumanGateOut["band"]>> = {
  decision: "decisions",
  sign_off_request: "sign_offs",
  proposal: "agent_outputs",
  send: "approvals_sends",
  final_approval: "approvals_sends",
  export: "approvals_sends",
  release: "approvals_sends",
  evidence_review: "approvals_sends",
};

interface GateRow {
  kind: Kind;
  subkind: string;
  client: string;
  title: string;
  context: string;
  due: string | null;
  blocked?: string;
}

function gate(persona: HomePersona, n: number, row: GateRow): HumanGateOut {
  const office = CLIENT_OFFICE[row.client];
  const id = stableId(`gate:${persona}:${String(n)}`);
  return {
    id,
    kind: row.kind,
    subkind: row.subkind,
    band: BAND_OF[row.kind],
    subject: { type: row.subkind, id: stableId(`gate-subject:${persona}:${String(n)}`) },
    engagement_id: stableId(`engagement:home:${slugOfClient(row.client)}`),
    work_item_id: null,
    client_id: clientId(row.client),
    assignee_user_id: userId(persona),
    role: null,
    due_on: row.due,
    state: "open",
    created_at: DEMO_INSTANT,
    office_id: office === undefined ? null : officeIdOf(office),
    blocked: row.blocked !== undefined,
    blocked_reason_code: row.blocked ?? null,
    title: row.title,
    context: row.context,
  };
}

const RIDGELINE = "Ridgeline Property Partners, LP";
const SIGN_OFF = "Partner sign-off — Ridgeline 2025 Form 1065";

/** HOME-01a: Daniel's eleven, verbatim (docs/screens/HOME-01.md, "Rows of a"). */
const DANIEL: readonly GateRow[] = [
  {
    kind: "decision",
    subkind: "decision_card",
    client: RIDGELINE,
    title: "§754 election — Ridgeline Property Partners, LP",
    context:
      "6/30/2025 transfer to Pell Street II LLC · §743(b) placeholder 28,595 · Accrued Agent recommends filing without the election",
    due: "2026-09-15",
  },
  {
    kind: "decision",
    subkind: "decision_card",
    client: "Marcus & Dana Whitley",
    title: "CP2000 position — Marcus & Dana Whitley, TY2024",
    context:
      "2 Forms 1099-INT not on the return: 1,870 + 1,250 = 3,120 · proposed tax 686.40 + interest 66.61 · recommended: agree",
    due: "2026-09-23",
  },
  {
    kind: "decision",
    subkind: "acceptance_decision_due",
    client: "Estate of Walter Thornbury",
    title: "Acceptance — Estate of Walter Thornbury (Form 706 · estate Form 1041)",
    context: "Pre-screened Sep 11 · Moderate risk · 3 flags · recommended: accept with conditions",
    due: "2026-11-02",
  },
  {
    kind: "sign_off_request",
    subkind: "return_section_sign_off",
    client: RIDGELINE,
    title: `${SIGN_OFF} · Summary & preparer memo`,
    context: "Reviewed · SI ✓",
    due: "2026-09-15",
  },
  {
    kind: "sign_off_request",
    subkind: "return_section_sign_off",
    client: RIDGELINE,
    title: `${SIGN_OFF} · Financials (TB → TTB)`,
    context: "AJE-1 18,500 · TJE-1 reclass 6,200 · Unmapped 0 · Reviewed · SI",
    due: "2026-09-15",
  },
  {
    kind: "sign_off_request",
    subkind: "return_section_sign_off",
    client: RIDGELINE,
    title: `${SIGN_OFF} · Schedule K`,
    context: "Box 2 1,231,600 · box 5 18,400 · 18A 6,200 · 19A 600,000 · Reviewed · SI",
    due: "2026-09-15",
  },
  {
    kind: "sign_off_request",
    subkind: "return_section_sign_off",
    client: RIDGELINE,
    title: `${SIGN_OFF} · Capital Accounts`,
    context: "M-2 ties · off 6,200 — fix proposed by Accrued Agent, awaiting Samuel Ito",
    due: "2026-09-15",
    blocked: "fix_awaiting_review",
  },
  {
    kind: "sign_off_request",
    subkind: "return_section_sign_off",
    client: RIDGELINE,
    title: `${SIGN_OFF} · Basis`,
    context: "Pell Street II off 28,595 — §743(b) placeholder, needs decision 1",
    due: "2026-09-15",
    blocked: "decision_pending",
  },
  {
    kind: "sign_off_request",
    subkind: "return_section_sign_off",
    client: RIDGELINE,
    title: `${SIGN_OFF} · States & PTET`,
    context: "IL 46.0% · CO 31.5% · NY 22.5% · PTET 28,044 / 17,070 / 18,982 · Reviewed · SI",
    due: "2026-09-15",
  },
  {
    kind: "final_approval",
    subkind: "return_final_approval",
    client: RIDGELINE,
    title: "Final approval & export — Ridgeline 2025 Form 1065 (BH-TAX-02)",
    context: "Unlocks after the 6 sign-offs → export to CCH Axcess → release 5 K-1s",
    due: "2026-09-15",
  },
  {
    kind: "send",
    subkind: "envelope_send",
    client: "Harborview Dental Properties, LP",
    title: "Send Form 8879-PE — Harborview Dental Properties, LP",
    context: "Ready · Synced Sep 11 · signer Dr. Sofia Lindqvist",
    due: "2026-09-15",
  },
];

/** HOME-01b (spec-only, TPL-11 content): Margaret's 4 = 2 + 2. */
const MARGARET: readonly GateRow[] = [
  {
    kind: "decision",
    subkind: "decision_card",
    client: "Northwind Robotics, Inc.",
    title: "Planning materiality — Northwind Robotics 401(k) Plan, PY2025",
    context:
      "Proposed v1 by Accrued Agent on unadjusted net assets $16,812,400: 1.0% = $168,100 or 1.5% = $252,200 (recommended). Blocking 3 workpapers.",
    due: null,
    blocked: "blocked_on_partner_decision",
  },
  {
    kind: "decision",
    subkind: "decision_card",
    client: "Granite Peak Outdoor Supply, Inc.",
    title: "Planning materiality — Granite Peak Outdoor Supply, Inc., FY2026",
    context:
      "Proposed by Accrued Agent: 5% of pre-tax income $3,100,000 = $155,000 · PM $116,250 · CT $7,750",
    due: null,
    blocked: "blocked_on_partner_decision",
  },
  {
    kind: "send",
    subkind: "engagement_letter_countersign",
    client: "Granite Peak Outdoor Supply, Inc.",
    title: "Countersign engagement letter — FY2026 FS audit · Granite Peak Outdoor Supply",
    context: "Luis Ferrante signed · your signature",
    due: "2026-09-16",
  },
  {
    kind: "send",
    subkind: "engagement_letter_countersign",
    client: "Fairhaven Foods 401(k) Plan",
    title: "Countersign engagement letter — PY2025 EBP audit · Fairhaven Foods 401(k) Plan",
    context: "Sent Sep 8 to the plan administrator and to you",
    due: "2026-09-18",
  },
];

/** HOME-01c (spec-only): Samuel's 6 = 0 + 4 + 2. */
const SAMUEL: readonly GateRow[] = [
  {
    kind: "sign_off_request",
    subkind: "return_section_sign_off",
    client: "Jonah & Claire Feld",
    title: "Feld 1040 Manager review",
    context: "Review 37, Issues 4",
    due: null,
  },
  {
    kind: "sign_off_request",
    subkind: "return_section_sign_off",
    client: "Calloway Family Trust",
    title: "Calloway Trust Calculation",
    context: "DNI 400,000",
    due: null,
  },
  {
    kind: "sign_off_request",
    subkind: "return_section_sign_off",
    client: "Calloway Family Trust",
    title: "Calloway Instrument interpretation",
    context: "",
    due: null,
  },
  {
    kind: "sign_off_request",
    subkind: "return_section_sign_off",
    client: RIDGELINE,
    title: "Ridgeline Capital Accounts re-review",
    context: "after the M-2 fix",
    due: null,
  },
  {
    kind: "proposal",
    subkind: "agent_proposal",
    client: RIDGELINE,
    title: "Approve M-2 fix — add tax-exempt interest 6,200 as other increase (Ridgeline)",
    context: "",
    due: null,
  },
  {
    kind: "proposal",
    subkind: "agent_proposal",
    client: "Jonah & Claire Feld",
    title: "Approve treatment — Ridgeline K-1 box 2 passive (Feld 1040)",
    context: "Prior-year treatment and the current K-1 support passive activity classification",
    due: null,
  },
];

/** HOME-01e (spec-only): Grace's 2 sends. */
const GRACE: readonly GateRow[] = [
  {
    kind: "send",
    subkind: "envelope_send",
    client: "Harborview Dental Properties, LP",
    title: "Send Form 8879-PE — Harborview",
    context: "",
    due: "2026-09-15",
  },
  {
    kind: "send",
    subkind: "portal_invite_resend",
    client: "Summit Plan Administrators",
    title: "Resend invite — Summit Plan Administrators (expires Sep 24)",
    context: "",
    due: "2026-09-24",
  },
];

const GATE_ROWS: Readonly<Record<HomePersona, readonly GateRow[]>> = {
  "daniel-reyes": DANIEL,
  "margaret-okonkwo": MARGARET,
  "samuel-ito": SAMUEL,
  "kevin-osei": [],
  "grace-holloway": GRACE,
  "hannah-leclerc": [],
  "marcus-delaney": [],
  "lena-park": [],
};

/** The open gates assigned to each persona at E0 (empty context lines read as none). */
export function homeGates(persona: string): HumanGateOut[] {
  const rows = GATE_ROWS[persona as HomePersona] ?? [];
  return rows.map((row, i) => {
    const g = gate(persona as HomePersona, i + 1, row);
    return g.context === "" ? { ...g, context: null } : g;
  });
}

// ---- Tiles --------------------------------------------------------------------------------------

const status = (code: string, n: number, filter: string) => ({ code, n, filter });
const byOffice = (chicago: number, denver: number, newYork: number) => [
  { office_id: officeIdOf("Chicago"), n: chicago },
  { office_id: officeIdOf("Denver"), n: denver },
  { office_id: officeIdOf("New York"), n: newYork },
];

/** The practice tiles at E0, firm-wide (blueprint §9.5): 79 open returns (2 + 8 + 9 + 17 + 15 +
 * 11 + 7 + 10), audits 27, closes 22, notices 9. By office: TY2025 returns 224 = 98 + 64 + 62
 * (TPL-11f). */
function firmTiles(): HomeTileOut[] {
  return [
    {
      key: "returns",
      label: "home.tile.returns",
      caption: "home.tile.returns.caption",
      total: 79,
      by_status: [
        status("not_started", 2, "status=not_started"),
        status("gathering", 8, "status=gathering"),
        status("preparing", 9, "status=preparing"),
        status("prepared", 17, "status=prepared"),
        status("in_review", 15, "status=in_review"),
        status("action_required", 11, "status=action_required"),
        status("approved", 7, "status=approved"),
        status("awaiting_signature", 10, "status=awaiting_signature"),
      ],
      by_office: byOffice(98, 64, 62),
      target: "/tax-returns",
    },
    {
      key: "audits",
      label: "home.tile.audits",
      caption: null,
      total: 27,
      by_status: [
        status("planning", 7, "phase=planning"),
        status("fieldwork", 9, "phase=fieldwork"),
        status("in_review", 6, "phase=in_review"),
        status("ready_to_release", 2, "phase=ready_to_release"),
        status("released", 3, "phase=released"),
      ],
      by_office: [],
      target: "/audits",
    },
    {
      key: "closes",
      label: "home.tile.closes",
      caption: "home.tile.closes.caption",
      total: 22,
      by_status: [
        status("not_started", 3, "status=not_started"),
        status("in_progress", 11, "status=in_progress"),
        status("in_review", 5, "status=in_review"),
        status("delivered", 3, "status=delivered"),
      ],
      by_office: [],
      target: "/closes",
    },
    {
      key: "notices",
      label: "home.tile.notices",
      caption: null,
      total: 9,
      by_status: [status("received", 2, "status=received")],
      by_office: [],
      target: "/notices",
    },
  ];
}

/** TPL-11f: the same tiles for the Denver office (64 returns; audits 9; closes 4 of 8; notices 3
 * with 1 new). The tax tile shows the four tile statuses only there. */
function denverTiles(): HomeTileOut[] {
  return [
    {
      key: "returns",
      label: "home.tile.returns",
      caption: "home.tile.returns.office",
      total: 64,
      by_status: [
        status("prepared", 5, "status=prepared"),
        status("in_review", 4, "status=in_review"),
        status("action_required", 3, "status=action_required"),
        status("approved", 2, "status=approved"),
      ],
      by_office: [],
      target: "/tax-returns",
    },
    {
      key: "audits",
      label: "home.tile.audits",
      caption: null,
      total: 9,
      by_status: [
        status("planning", 2, "phase=planning"),
        status("fieldwork", 3, "phase=fieldwork"),
        status("in_review", 2, "phase=in_review"),
        status("ready_to_release", 1, "phase=ready_to_release"),
        status("released", 1, "phase=released"),
      ],
      by_office: [],
      target: "/audits",
    },
    {
      key: "closes",
      label: "home.tile.closes",
      caption: "home.tile.closes.caption",
      total: 8,
      by_status: [status("in_progress", 4, "status=in_progress")],
      by_office: [],
      target: "/closes",
    },
    {
      key: "notices",
      label: "home.tile.notices",
      caption: null,
      total: 3,
      by_status: [status("received", 1, "status=received")],
      by_office: [],
      target: "/notices",
    },
  ];
}

/** HOME-01e: the firm admin's counts-only tiles (ADR-024). */
function adminTiles(): HomeTileOut[] {
  const stat = (key: string, total: number, target: string): HomeTileOut => ({
    key,
    label: `home.tile.${key}`,
    caption: null,
    total,
    by_status: [],
    by_office: [],
    target,
  });
  return [
    stat("signatures_out", 17, "/signatures"),
    stat("inbox_waiting", 23, "/inbox"),
    stat("portal_invites_pending", 2, "/clients"),
    stat("binders", 241, "/binders"),
  ];
}

// ---- Your work and deadlines ----------------------------------------------------------------------

const work = (n: number, name: string, client: string, code: string, tags: string[] = []) => ({
  work_item_id: stableId(`home:work:${client}:${String(n)}`),
  name,
  client,
  status: code,
  function: null,
  tags,
});

/** a2 "Your returns 6"; b "Your engagements" 4; d "My work" 4. */
const YOUR_WORK: Partial<Record<HomePersona, HomeOut["your_work"]>> = {
  "daniel-reyes": {
    label: "home.your_work.returns",
    rows: [
      work(1, "2025 Form 1065", RIDGELINE, "in_review"),
      work(2, "2025 Form 1065", "Harborview Dental Properties, LP", "approved"),
      work(3, "2025 Form 1041", "Calloway Family Trust", "prepared"),
      work(4, "2025 Form 1040", "Jonah & Claire Feld", "in_review", ["Draft K-1 · pre-release"]),
      work(5, "2025 Form 1040", "Estate of Walter Thornbury", "gathering"),
      work(6, "CP2000 TY2024", "Marcus & Dana Whitley", "analyzing"),
    ],
  },
  "margaret-okonkwo": {
    label: "home.your_work.engagements",
    rows: [
      work(1, "PY2025 EBP audit", "Northwind Robotics 401(k) Plan", "planning"),
      work(2, "FY2026 FS audit", "Granite Peak Outdoor Supply, Inc.", "planning"),
      work(3, "PY2025 EBP audit", "Fairhaven Foods 401(k) Plan", "planning"),
      work(4, "PY2025 EBP audit", "Arbor Senior Living 401(k) Plan", "fieldwork"),
    ],
  },
  "kevin-osei": {
    label: "home.your_work.mine",
    rows: [
      work(1, "2025 Form 1040", "Jonah & Claire Feld", "in_review"),
      work(2, "CP2000 TY2024", "Marcus & Dana Whitley", "analyzing"),
      work(3, "2025 Form 1040", "Sunil & Asha Rao", "filed"),
      work(4, "2 attachments waiting in Inbox", "Jonah & Claire Feld", "gathering"),
    ],
  },
};

const deadline = (n: number, due: string, client: string, filing: string, code: string) => ({
  work_item_id: stableId(`home:deadline:${String(n)}`),
  due_on: due,
  client,
  filing_label: filing,
  status: code,
  risk: due <= "2026-09-21" ? ("due_soon" as const) : ("approaching" as const),
});

/** HOME-01a "Your deadlines · next 14 days" and the next one past it. */
function danielDeadlines(): HomeOut["deadlines"] {
  return {
    rows: [
      deadline(1, "2026-09-15", RIDGELINE, "Form 1065 (extended, Form 7004)", "in_review"),
      deadline(
        2,
        "2026-09-15",
        "Harborview Dental Properties, LP",
        "Form 8879-PE to send",
        "approved",
      ),
      deadline(3, "2026-09-23", "Marcus & Dana Whitley", "CP2000 response, TY2024", "analyzing"),
      deadline(4, "2026-09-24", RIDGELINE, "Engagement letter — cost segregation & §754", "sent"),
    ],
    next: {
      ...deadline(5, "2026-09-30", "Calloway Family Trust", "Form 1041 (extended)", "prepared"),
      risk: "later",
    },
  };
}

const FIRST_NAME: Readonly<Record<HomePersona, string>> = {
  "daniel-reyes": "Daniel",
  "margaret-okonkwo": "Margaret",
  "samuel-ito": "Samuel",
  "kevin-osei": "Kevin",
  "grace-holloway": "Grace",
  "hannah-leclerc": "Hannah",
  "marcus-delaney": "Marcus",
  "lena-park": "Lena",
};

/** `GET /v1/home` for a persona at E0, for every office or one (`officeName`). */
export function homeView(persona: string, officeName: OfficeName | null = null): HomeOut {
  const who = persona as HomePersona;
  const admin = who === "grace-holloway";
  return {
    greeting: { first_name: FIRST_NAME[who] ?? "", date: HOME_TODAY },
    tiles: admin ? adminTiles() : officeName === "Denver" ? denverTiles() : firmTiles(),
    your_work: YOUR_WORK[who] ?? null,
    deadlines: who === "daniel-reyes" ? danielDeadlines() : { rows: [], next: null },
    // Client activity is I-01-T12's projection; its rows arrive with it.
    client_activity: [],
    running_count: admin ? null : 3,
    segments: { deadlines: "planned", capacity: "planned", insights: "entitlement_missing" },
  };
}

export const HOME_PERSONAS: readonly HomePersona[] = Object.keys(FIRST_NAME) as HomePersona[];
