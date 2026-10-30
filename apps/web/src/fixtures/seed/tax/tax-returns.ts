// The TY2025 practice board at E0, Mon Sep 14, 2026, 9:24 AM CT (F-06-T02; F-06.md §5.3,
// docs/screens/TPL-01.md): 224 returns, 79 open and 145 done, 161 extended (blueprint 01 §9.5).
//
// The roster mirrors the Python scenario's `binders.build_returns` (abacus_tools.synthetic.
// scenarios.brightwater_hale.binders), so the gallery and the loaded tenant hold the same returns:
// every tax client has one return (the form §9.3 or §9.7 gives it, else its kind's form), and
// filler clients take a second return by office until the offices read 98 / 64 / 62 (§9.1). The
// statuses, people, sync chips and due dates of the named returns are TPL-01's rows (a, b) and
// §9.7 R1 to R30; the rest are settled by stable rank so the §9.5 tiles foot. Once the Python
// scenario covers the tax epoch these rows are exported from it (FE-11).

import { buildClients, type ClientKind, type SeedClient, slugOfClient } from "../clients";
import { type OfficeName, SEATS } from "../people";
import { stableId } from "../prng";

export const TAX_YEAR = 2025;

export type TaxForm = "1040" | "1041" | "1065" | "1120-S" | "1120" | "990" | "990-PF";

/** `return` codes of docs/product/status-vocabulary.yaml. */
export type TaxReturnStatus =
  | "not_started"
  | "gathering"
  | "preparing"
  | "prepared"
  | "in_review"
  | "action_required"
  | "approved"
  | "awaiting_signature"
  | "filed"
  | "accepted";

export type ReviewLevel = "Detail" | "Manager" | "Partner";

/** `return_sync_chip` codes; `synced` carries its date. */
export type SyncChip =
  { code: "not_yet_exported" } | { code: "ready_for_export" } | { code: "synced"; date: string };

export interface SeedTaxReturn {
  id: string;
  /** "<client slug>" or "<client slug>:2" (the Python label). */
  label: string;
  client: string;
  form: TaxForm;
  office: OfficeName;
  /** Initials of the preparer and reviewer (TPL-01 "Prep / Rev"). */
  preparer: string;
  reviewer: string;
  status: TaxReturnStatus;
  level: ReviewLevel | null;
  /** Open issues on the return; null renders "—". */
  issues: number | null;
  sync: SyncChip;
  /** ISO date of the due date the row shows (the extended date when extended). */
  due: string;
  extended: boolean;
  /** The rule string the due cell's popover reads (C21 rules tables, K-02). */
  dueRule: string;
  tag: string | null;
  /** The 8879-family envelope behind an Awaiting signature return (E1 to E10). */
  envelope: string | null;
}

export const RETURNS_TOTAL = 224;
export const OPEN_TOTAL = 79;
export const EXTENDED_TOTAL = 161;
export const RETURNS_BY_OFFICE: Readonly<Record<OfficeName, number>> = {
  Chicago: 98,
  Denver: 64,
  "New York": 62,
};

/** §9.5: open 79 by status (Not started has no tile), done 145. */
export const STATUS_COUNTS: Readonly<Record<TaxReturnStatus, number>> = {
  not_started: 2,
  gathering: 8,
  preparing: 9,
  prepared: 17,
  in_review: 15,
  action_required: 11,
  approved: 7,
  awaiting_signature: 10,
  filed: 6,
  accepted: 139,
};

export const OPEN_STATUSES: readonly TaxReturnStatus[] = [
  "not_started",
  "gathering",
  "preparing",
  "prepared",
  "in_review",
  "action_required",
  "approved",
  "awaiting_signature",
];

/** TAX-01's tile order (DEC-801): the first four, then the rest. */
export const TILE_ORDER = [
  "prepared",
  "in_review",
  "action_required",
  "approved",
  "gathering",
  "preparing",
  "awaiting_signature",
  "filed_accepted",
] as const;

// --- forms the sources give, as the Python _KNOWN (true: done) ---------------------------------

const KNOWN: Readonly<Record<string, readonly [TaxForm, boolean]>> = {
  "Jonah & Claire Feld": ["1040", false],
  "Copperleaf Coffee Roasters, Inc.": ["1120-S", true],
  "Meera Shah": ["1040", false],
  "Ridgeline Property Partners, LP": ["1065", false],
  "Harborview Dental Properties, LP": ["1065", false],
  "Marcus & Dana Whitley": ["1040", true],
  "Estate of Walter Thornbury": ["1040", false],
  "Bluestem Analytics, LLC": ["1120-S", true],
  "Lakeshore Literacy Alliance": ["990", false],
  "Elena Varga": ["1040", false],
  "Calloway Family Trust": ["1041", false],
  "Ashford Manufacturing Co.": ["1120", false],
  "Daniel & Ruth Okafor": ["1040", true],
  "Mateo & Lucia Alvarez": ["1040", true],
  "Priyanka & Sam Iyer": ["1040", false],
  "Harold Stein": ["1040", false],
  "Wren & Avery Collins": ["1040", false],
  "Gloria Mendez": ["1040", false],
  "Thomas & Irene Kowal": ["1040", false],
  "Benjamin Osterberg": ["1040", false],
  "Nina & Paul Haddox": ["1040", false],
  "Rafael Quintero": ["1040", false],
  "Sunil & Asha Rao": ["1040", true],
  "Cedar Hollow Farms, LLC": ["1065", true],
  "Northgate Medical Partners, LLP": ["1065", false],
  "Marlowe Street Holdings, LP": ["1065", false],
  "Kestrel Ventures Fund I, LP": ["1065", false],
  "Bramble & Finch Design, LLC": ["1065", false],
  "Two Rivers Brewing Co.": ["1120-S", true],
  "Summit Line Logistics, Inc.": ["1120-S", true],
  "Pinecrest Pediatrics, PC": ["1120-S", false],
  "Oakline Software, Inc.": ["1120", false],
  "Meridian Tool & Die, Inc.": ["1120", false],
  "Fenwick Family Foundation": ["990-PF", false],
  "Riverbend Community Theater": ["990", false],
  "Pryor Irrevocable Trust": ["1041", false],
  "Estate of Eugene Barlow": ["1041", false],
  "Delia Fortune": ["1040", true],
  "Morgan & Kai Ferris": ["1040", false],
  "Aurelio Santos": ["1040", false],
  "Hollis Creek Veterinary, PC": ["1120-S", false],
  "Vantage Point Realty, LLC": ["1065", true],
  "Juliet Okonjo": ["1040", false],
  "Larkspur Floral, Inc.": ["1120-S", false],
  "Corinne Abbott": ["1040", false],
  "Dev & Mira Kapoor": ["1040", false],
  "Hugo Brandvold": ["1040", false],
  "Noor & Adam Farouk": ["1040", false],
  "Brightline Optics, Inc.": ["1120", false],
};

const FORM_OF_KIND: Partial<Readonly<Record<ClientKind, TaxForm>>> = {
  individual: "1040",
  household: "1040",
  business: "1120-S",
  partnership: "1065",
};

// --- the named rows: TPL-01 a and b, §9.7 R1 to R30, §9.3 --------------------------------------

interface Named {
  office?: OfficeName;
  team: string; // "OB / SI"
  status: TaxReturnStatus;
  level?: ReviewLevel;
  issues?: number;
  sync?: SyncChip;
  extended?: boolean;
  /** The due date when it is not the form's extended (or original) date. */
  due?: string;
  tag?: string;
  envelope?: string;
}

const NYE: SyncChip = { code: "not_yet_exported" };
const RFE: SyncChip = { code: "ready_for_export" };
const synced = (date: string): SyncChip => ({ code: "synced", date });

const NAMED: Readonly<Record<string, Named>> = {
  // TPL-01a rows 1 to 15
  "Ridgeline Property Partners, LP": {
    office: "New York",
    team: "OB / SI",
    status: "in_review",
    level: "Partner",
    issues: 11,
    sync: NYE,
  },
  "Harborview Dental Properties, LP": {
    office: "New York",
    team: "DS / TR",
    status: "approved",
    sync: synced("Sep 11"),
  },
  "Northgate Medical Partners, LLP": {
    office: "Chicago",
    team: "BN / NA",
    status: "in_review",
    level: "Manager",
    issues: 2,
    sync: NYE,
  },
  "Marlowe Street Holdings, LP": {
    office: "New York",
    team: "DS / TR",
    status: "action_required",
    issues: 3,
    sync: NYE,
  },
  "Kestrel Ventures Fund I, LP": {
    office: "New York",
    team: "NP / TR",
    status: "awaiting_signature",
    sync: synced("Sep 11"),
    envelope: "E3",
  },
  "Bramble & Finch Design, LLC": {
    office: "Chicago",
    team: "GT / YK",
    status: "prepared",
    issues: 1,
    sync: NYE,
  },
  "Hollis Creek Veterinary, PC": {
    office: "Denver",
    team: "JL / OB",
    status: "in_review",
    level: "Detail",
    issues: 2,
    sync: NYE,
  },
  "Pinecrest Pediatrics, PC": { office: "Denver", team: "LP / OB", status: "approved", sync: RFE },
  "Calloway Family Trust": { office: "Chicago", team: "KO / SI", status: "prepared", sync: NYE },
  "Pryor Irrevocable Trust": {
    office: "Chicago",
    team: "MA / YK",
    status: "awaiting_signature",
    sync: synced("Sep 10"),
    envelope: "E4",
  },
  "Jonah & Claire Feld": {
    office: "New York",
    team: "KO / SI",
    status: "in_review",
    level: "Manager",
    issues: 4,
    sync: synced("Sep 10"),
  },
  "Meera Shah": {
    office: "Chicago",
    team: "LP / SI",
    status: "preparing",
    sync: NYE,
    tag: "Waiting on K-1",
  },
  "Ashford Manufacturing Co.": {
    office: "Chicago",
    team: "YK / NA",
    status: "in_review",
    level: "Manager",
    issues: 2,
    sync: NYE,
  },
  "Elena Varga": {
    office: "Chicago",
    team: "LP / OB",
    status: "awaiting_signature",
    sync: synced("Sep 8"),
    envelope: "E1",
  },
  "Estate of Walter Thornbury": {
    office: "Chicago",
    team: "BN / YK",
    status: "gathering",
    sync: NYE,
  },
  // TPL-01b, the other Awaiting signature returns
  "Larkspur Floral, Inc.": {
    office: "Chicago",
    team: "GT / YK",
    status: "awaiting_signature",
    envelope: "E7",
  },
  "Thomas & Irene Kowal": {
    office: "Chicago",
    team: "MA / YK",
    status: "awaiting_signature",
    envelope: "E2",
  },
  "Corinne Abbott": {
    office: "Denver",
    team: "JL / IM",
    status: "awaiting_signature",
    envelope: "E5",
  },
  "Dev & Mira Kapoor": {
    office: "New York",
    team: "DS / QL",
    status: "awaiting_signature",
    envelope: "E6",
  },
  "Hugo Brandvold": {
    office: "Denver",
    team: "NK / OB",
    status: "awaiting_signature",
    envelope: "E8",
  },
  "Noor & Adam Farouk": {
    office: "New York",
    team: "RV / NP",
    status: "awaiting_signature",
    envelope: "E9",
  },
  "Brightline Optics, Inc.": {
    office: "Chicago",
    team: "BN / NA",
    status: "awaiting_signature",
    envelope: "E10",
  },
  // §9.7 R1 to R30 not already above
  "Mateo & Lucia Alvarez": {
    office: "Chicago",
    team: "BN / YK",
    status: "accepted",
    extended: false,
  },
  "Priyanka & Sam Iyer": {
    office: "New York",
    team: "DS / QL",
    status: "in_review",
    level: "Manager",
  },
  "Harold Stein": { office: "Chicago", team: "GT / YK", status: "action_required" },
  "Wren & Avery Collins": { office: "Denver", team: "JL / IM", status: "prepared" },
  "Gloria Mendez": { office: "Denver", team: "NK / OB", status: "gathering" },
  "Benjamin Osterberg": { office: "New York", team: "RV / NP", status: "preparing" },
  "Nina & Paul Haddox": { office: "Chicago", team: "PS / YK", status: "approved" },
  "Rafael Quintero": { office: "Denver", team: "LW / OB", status: "not_started" },
  "Sunil & Asha Rao": {
    office: "New York",
    team: "KO / QL",
    status: "filed",
    sync: synced("Sep 11"),
  },
  "Cedar Hollow Farms, LLC": { office: "Denver", team: "JL / IM", status: "accepted" },
  "Two Rivers Brewing Co.": { office: "Denver", team: "LW / IM", status: "accepted" },
  "Summit Line Logistics, Inc.": {
    office: "Chicago",
    team: "BN / YK",
    status: "filed",
    sync: synced("Sep 12"),
  },
  "Oakline Software, Inc.": {
    office: "New York",
    team: "QL / TR",
    status: "in_review",
    level: "Partner",
  },
  "Meridian Tool & Die, Inc.": { office: "Chicago", team: "YK / NA", status: "preparing" },
  "Fenwick Family Foundation": { office: "Chicago", team: "BN / NA", status: "gathering" },
  "Riverbend Community Theater": { office: "Denver", team: "NK / IM", status: "prepared" },
  "Estate of Eugene Barlow": {
    office: "New York",
    team: "RV / QL",
    status: "in_review",
    level: "Manager",
  },
  "Delia Fortune": { office: "Denver", team: "LP / OB", status: "accepted", extended: false },
  "Morgan & Kai Ferris": { office: "New York", team: "DS / NP", status: "gathering" },
  "Aurelio Santos": { office: "Chicago", team: "PS / YK", status: "action_required" },
  "Vantage Point Realty, LLC": { office: "Chicago", team: "GT / NA", status: "accepted" },
  "Juliet Okonjo": { office: "Chicago", team: "BN / YK", status: "prepared" },
  // §9.3 named clients not in the tables above
  "Copperleaf Coffee Roasters, Inc.": { team: "LW / IM", status: "accepted", extended: false },
  "Marcus & Dana Whitley": {
    team: "KO / SI",
    status: "accepted",
    extended: false,
    sync: synced("Apr 10"),
  },
  "Bluestem Analytics, LLC": { team: "QL / TR", status: "accepted", extended: false },
  "Daniel & Ruth Okafor": { team: "BN / YK", status: "accepted", extended: false },
  // §9.3: the FYE Jun 30, 2026 990 is due Nov 16, 2026 on its original date (8868 available).
  "Lakeshore Literacy Alliance": {
    team: "BN / NA",
    status: "gathering",
    extended: false,
    due: "2026-11-16",
  },
};

// --- due dates (extended where the return is on extension) -----------------------------------

const DUE: Readonly<Record<TaxForm, { original: string; extended: string; rule: string }>> = {
  "1040": {
    original: "2026-04-15",
    extended: "2026-10-15",
    rule: "15th day, 4th month + 6 months",
  },
  "1041": {
    original: "2026-04-15",
    extended: "2026-09-30",
    rule: "15th day, 4th month + 5½ months",
  },
  "1065": {
    original: "2026-03-16",
    extended: "2026-09-15",
    rule: "15th day, 3rd month + 6 months",
  },
  "1120-S": {
    original: "2026-03-16",
    extended: "2026-09-15",
    rule: "15th day, 3rd month + 6 months",
  },
  "1120": {
    original: "2026-04-15",
    extended: "2026-10-15",
    rule: "15th day, 4th month + 6 months",
  },
  "990": {
    original: "2026-05-15",
    extended: "2026-11-16",
    rule: "15th day, 5th month + 6 months",
  },
  "990-PF": {
    original: "2026-05-15",
    extended: "2026-11-16",
    rule: "15th day, 5th month + 6 months",
  },
};

// --- the roster, as the Python build_returns ---------------------------------------------------

interface Slot {
  label: string;
  client: SeedClient;
  form: TaxForm;
  office: OfficeName;
}

function rank(label: string): string {
  return stableId(`rank:${label}`);
}

function taxClients(): SeedClient[] {
  return buildClients().filter((c) => c.services.includes("tax"));
}

function formOf(c: SeedClient): TaxForm {
  const known = KNOWN[c.name];
  if (known !== undefined) return known[0];
  const form = FORM_OF_KIND[c.kind];
  if (form === undefined) throw new Error(`no form for ${c.name} (${c.kind})`);
  return form;
}

function roster(): Slot[] {
  const clients = taxClients();
  // A named return's office is the board's (TPL-01, §9.7), which the office quota counts.
  const first: Slot[] = clients.map((c) => ({
    label: slugOfClient(c.name),
    client: c,
    form: formOf(c),
    office: NAMED[c.name]?.office ?? c.office,
  }));
  const need = new Map<OfficeName, number>(
    (Object.keys(RETURNS_BY_OFFICE) as OfficeName[]).map((o) => [
      o,
      RETURNS_BY_OFFICE[o] - first.filter((s) => s.office === o).length,
    ]),
  );
  const extras: Slot[] = [];
  for (const c of clients) {
    const left = need.get(c.office) ?? 0;
    if (c.origin !== "filler" || left <= 0) continue;
    need.set(c.office, left - 1);
    extras.push({
      label: `${slugOfClient(c.name)}:2`,
      client: c,
      form: formOf(c),
      office: c.office,
    });
  }
  return [...first, ...extras];
}

// --- statuses ------------------------------------------------------------------------------------

/** The levels an unnamed In review return takes, in rank order. */
const LEVELS: readonly ReviewLevel[] = ["Detail", "Manager", "Partner"];
const SYNC_DAYS = ["Sep 8", "Sep 9", "Sep 10", "Sep 11"];

function seatsOf(office: OfficeName, role: "Tax Preparer" | "Tax Reviewer"): string[] {
  return SEATS.filter((s) => s.office === office && s.role === role).map((s) => s.initials);
}

function pick<T>(items: readonly T[], label: string, salt: string): T {
  const hex = stableId(`${salt}:${label}`).slice(0, 8);
  const item = items[Number.parseInt(hex, 16) % items.length];
  if (item === undefined) throw new Error(`nothing to pick for ${label}`);
  return item;
}

function build(): SeedTaxReturn[] {
  const slots = roster();
  const isNamed = (s: Slot): boolean => !s.label.endsWith(":2") && s.client.name in NAMED;
  // Unnamed statuses: what the named rows leave of §9.5, assigned by stable rank (open first).
  const left = new Map<TaxReturnStatus, number>(
    (Object.keys(STATUS_COUNTS) as TaxReturnStatus[]).map((st) => [st, STATUS_COUNTS[st]]),
  );
  for (const s of slots.filter(isNamed)) {
    const st = (NAMED[s.client.name] as Named).status;
    left.set(st, (left.get(st) ?? 0) - 1);
  }
  const queue: TaxReturnStatus[] = (Object.keys(STATUS_COUNTS) as TaxReturnStatus[]).flatMap(
    (st) => Array.from({ length: Math.max(0, left.get(st) ?? 0) }, () => st),
  );
  const unnamed = slots
    .filter((s) => !isNamed(s))
    .sort((a, b) => (rank(a.label) < rank(b.label) ? -1 : 1));
  const statusOf = new Map<string, TaxReturnStatus>(
    unnamed.map((s, n) => [s.label, queue[n] ?? "accepted"]),
  );
  // Extended: every open return and 82 filed on extension (§9.5); the unnamed done returns
  // take extension by rank until the count foots.
  const namedExtended = slots.filter(isNamed).filter((s) => {
    const n = NAMED[s.client.name] as Named;
    return n.extended ?? true;
  }).length;
  let extendLeft =
    EXTENDED_TOTAL -
    namedExtended -
    unnamed.filter((s) => OPEN_STATUSES.includes(statusOf.get(s.label) as TaxReturnStatus)).length;

  let levelAt = 0;
  return slots.map((s): SeedTaxReturn => {
    const named = isNamed(s) ? (NAMED[s.client.name] as Named) : null;
    const status: TaxReturnStatus = named?.status ?? statusOf.get(s.label) ?? "accepted";
    const open = OPEN_STATUSES.includes(status);
    let extended: boolean;
    if (named !== null) extended = named.extended ?? true;
    else if (open) extended = true;
    else {
      extended = extendLeft > 0;
      if (extended) extendLeft -= 1;
    }
    const rule = DUE[s.form];
    const office = named?.office ?? s.office;
    const [preparer, reviewer] =
      named !== null
        ? (named.team.split(" / ") as [string, string])
        : [
            pick(seatsOf(office, "Tax Preparer"), s.label, "prep"),
            pick(seatsOf(office, "Tax Reviewer"), s.label, "rev"),
          ];
    let level: ReviewLevel | null = named?.level ?? null;
    if (status === "in_review" && level === null) {
      level = LEVELS[levelAt % LEVELS.length] as ReviewLevel;
      levelAt += 1;
    }
    const sync: SyncChip =
      named?.sync ??
      (open ? (status === "approved" ? RFE : NYE) : synced(pick(SYNC_DAYS, s.label, "sync")));
    return {
      id:
        s.label === "jonah-and-claire-feld"
          ? stableId("work-item:feld")
          : stableId(`work-item:return:${s.label}`),
      label: s.label,
      client: s.client.name,
      form: s.form,
      office,
      preparer,
      reviewer,
      status,
      level,
      issues: named?.issues ?? null,
      sync,
      due: named?.due ?? (extended ? rule.extended : rule.original),
      extended,
      dueRule: extended ? rule.rule : rule.rule.replace(/ \+ .*$/, ""),
      tag: named?.tag ?? null,
      envelope: named?.envelope ?? null,
    };
  });
}

export const TAX_RETURNS: readonly SeedTaxReturn[] = build();

/** The named returns in the order TPL-01 draws them (rows a 1 to 15, then b's others). */
const NAMED_ORDER: readonly string[] = Object.keys(NAMED);

/** The open returns in board order (TPL-01a): the named returns as the handoff lists them, then
 * the rest by extended due date, then client. */
export function boardOrder(rows: readonly SeedTaxReturn[]): SeedTaxReturn[] {
  const rank = (r: SeedTaxReturn): number => {
    const i = NAMED_ORDER.indexOf(r.client);
    return i === -1 ? NAMED_ORDER.length : i;
  };
  return [...rows].sort((a, b) => {
    const named = rank(a) - rank(b);
    if (named !== 0) return named;
    return a.due === b.due ? a.client.localeCompare(b.client) : a.due < b.due ? -1 : 1;
  });
}
