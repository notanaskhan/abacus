// The portal PBC seed (R-01-T05): POR-03's binders, POR-04's requests and POR-14's rooms, typed
// with the generated client (C5 section portal-pbc). Every row, file name, date and note is from
// the handoff (docs/screens/POR-03.md, POR-04.md, POR-14.md); counts are the seed's own figures,
// never restated: the Feld binder's 21 = 19 + 2 and 37 sorted are POR-02's `FELD_BINDER`, the two
// open requests are the request seed's Intake 2, and Keystone's 9 are POR-01's delegations.
// Only the rows the handoff draws are itemized: the Feld binder's other 14 done requests,
// Dana's 4 undrawn requests and the file names behind POR-03 i's and POR-14's receipts (the
// handoff names none) arrive with R-01-T11's Python slice (docs/screens/POR-03.md, Open gaps).
// Until then those rows carry their receipt in their state and no file, so no Withdraw renders.

import type {
  CommentOut,
  DropBatchOut,
  PortalBinderOut,
  PortalBinderRefOut,
  PortalCategoryOut,
  PortalFileOut,
  PortalGroupOut,
  PortalRequestOut,
  PortalRoomOut,
  PortalRoomRowOut,
  PortalRowOut,
} from "@abacus/api-client";
import { prose } from "@abacus/ui";
import { getSeed } from ".";
import { KEYSTONE_DELEGATED, NORTHWIND_DELEGATIONS } from "../scenarios/POR-01";
import { FELD_BINDER } from "./portal-home";
import { PORTAL_USERS } from "./portal";
import { stableId } from "./prng";

const id = (key: string): string => stableId(`portal-pbc:${key}`);
const seed = getSeed();
const userId = (slug: string): string => stableId(`user:${slug}`);
const portalUser = (slug: string): string =>
  PORTAL_USERS.find((u) => u.slug === slug)?.id ?? userId(slug);

/** The Feld household's TY2025 engagement and its seeded request items (by title). */
const FELD_ENGAGEMENT = seed.engagementIds.feld ?? id("engagement:feld");
const feldItem = (title: string): string =>
  (seed.requestItems[FELD_ENGAGEMENT] ?? []).find((r) => r.description === title)?.id ??
  id(`item:${title}`);

export const FELD = {
  engagement: FELD_ENGAGEMENT,
  binder: stableId("binder:feld-2025"), // POR-02's binder id (seed/portal-home.ts)
  binder2024: id("binder:feld-2024"),
  w2: feldItem("2025 W-2 From Mercer Hill Health"),
  consolidated1099: feldItem("2025 Consolidated 1099 From Halvard Securities (Acct ••3318)"),
  k1: feldItem("Schedule K-1 from Ridgeline Property Partners, LP"),
  form1098: feldItem("2025 Form 1098 From Hudson Mutual Savings (co-op loan)"),
  form1095c: feldItem("Form 1095-C From Mercer Hill Health"),
  donations: feldItem("2025 donation receipts and acknowledgment letters"),
  estimates: feldItem(
    "2025 federal (1040-ES) and New York (IT-2105) estimated payment confirmations",
  ),
  dropBatch: id("drop:feld-0914"),
} as const;

/** The files the handoff names, with the receipts and sizes it shows. */
const file = (
  key: string,
  name: string,
  receipt: PortalFileOut["receipt"],
  extra: Partial<PortalFileOut> = {},
): PortalFileOut => ({
  id: id(`file:${key}`),
  name,
  receipt,
  withdrawable: receipt.kind === "uploaded" || receipt.kind === "rule_linked_pending",
  ...extra,
});

export const FELD_FILES = {
  w2: file("w2", "Claire_Feld_2025_W2_MercerHill.pdf", { kind: "emailed", on: "2026-08-03" }),
  consolidated1099: file("1099", "Jonah_Feld_2025_1099_Composite_Halvard.pdf", {
    kind: "uploaded_by_other_contact",
    on: "2026-08-05",
    by_first_name: "Jonah",
  }),
  form1098: file("1098", "Claire_Feld_2025_1098_HudsonMutual.pdf", {
    kind: "emailed",
    on: "2026-08-03",
  }),
  donations: file("donations", "Feld_2025_Donations.pdf", { kind: "uploaded", on: "2026-08-07" }),
  estimates: file(
    "estimates",
    "Feld_2025_Estimated_Payments.pdf",
    { kind: "rule_linked_pending", on: "2026-09-14" },
    { size_bytes: 1_100_000 },
  ),
  it2105: file(
    "it2105",
    "Feld_2025_IT2105_Confirmations.pdf",
    { kind: "rule_linked_pending", on: "2026-09-14" },
    { size_bytes: 380_000 },
  ),
  emailed1095c: file(
    "1095c-2025",
    "Feld_1095C_2025.pdf",
    { kind: "emailed", on: "2026-09-14" },
    { size_bytes: 412_000 },
  ),
  uploaded1095c: file(
    "1095c-2025-portal",
    "Feld_1095C_2025.pdf",
    { kind: "uploaded", on: "2026-09-14" },
    { size_bytes: 412_000 },
  ),
  returned1095c: file(
    "1095c-2024",
    "Feld_1095C_2024.pdf",
    { kind: "uploaded", on: "2026-09-14" },
    { withdrawable: false, struck: true },
  ),
  scan: { id: id("file:scan-0914"), name: "Scan_0914.pdf" },
} as const;

/** POR-03 a's rail: the two files uploading from Claire's browser (client-side progress). */
export const FELD_UPLOADS_IN_FLIGHT = [
  { name: "Feld_2025_Estimated_Payments.pdf", sizeBytes: 1_100_000, percent: 64 },
  { name: "Feld_2025_IT2105_Confirmations.pdf", sizeBytes: 380_000, percent: 38 },
] as const;
/** POR-04 g: the 1095-C held at 46%. */
export const SHEET_UPLOAD_PERCENT = 46;
/** POR-03 b and motion: the three files of Claire's 9:24 AM drop. */
export const FELD_DROP_FILES = [
  "Feld_2025_Estimated_Payments.pdf",
  "Feld_2025_IT2105_Confirmations.pdf",
  "Scan_0914.pdf",
] as const;

const KEVIN = "Kevin Osei";
const OPEN: NonNullable<PortalRowOut["allowed_actions"]> = ["upload", "ignore", "comment"];

/** The seven groups with activity under "Requested" (POR-03 a), in the handoff's order. */
const ROWS_A = {
  w2: {
    id: FELD.w2,
    engagement_id: FELD.engagement,
    title: "2025 W-2 From Mercer Hill Health",
    kind: "request",
    client_status: "done",
    files: [FELD_FILES.w2],
    allowed_actions: ["comment"],
  },
  consolidated1099: {
    id: FELD.consolidated1099,
    engagement_id: FELD.engagement,
    title: "2025 Consolidated 1099 From Halvard Securities (Acct ••3318)",
    kind: "request",
    client_status: "done",
    files: [FELD_FILES.consolidated1099],
    allowed_actions: ["comment"],
  },
  k1: {
    id: FELD.k1,
    engagement_id: FELD.engagement,
    title: "Schedule K-1 from Ridgeline Property Partners, LP",
    kind: "firm_provided",
    client_status: "done",
    allowed_actions: [],
  },
  form1098: {
    id: FELD.form1098,
    engagement_id: FELD.engagement,
    title: "2025 Form 1098 From Hudson Mutual Savings (co-op loan)",
    kind: "request",
    client_status: "done",
    files: [FELD_FILES.form1098],
    allowed_actions: ["comment"],
  },
  form1095c: {
    id: FELD.form1095c,
    engagement_id: FELD.engagement,
    title: "Form 1095-C From Mercer Hill Health",
    kind: "request",
    client_status: "to_do",
    allowed_actions: OPEN,
  },
  donations: {
    id: FELD.donations,
    engagement_id: FELD.engagement,
    title: "2025 donation receipts and acknowledgment letters",
    kind: "request",
    client_status: "done",
    files: [FELD_FILES.donations],
    allowed_actions: ["withdraw", "comment"],
  },
  estimates: {
    id: FELD.estimates,
    engagement_id: FELD.engagement,
    title: "2025 federal (1040-ES) and New York (IT-2105) estimated payment confirmations",
    kind: "request",
    client_status: "to_do",
    uploading_count: 2,
    allowed_actions: OPEN,
  },
} satisfies Record<string, PortalRowOut>;

type FeldRows = Record<keyof typeof ROWS_A, PortalRowOut>;

const GROUPS: readonly (readonly [string, string, string, keyof FeldRows])[] = [
  ["w2s", "W-2s", "income", "w2"],
  ["1099s", "1099s (all types), interest, dividends", "income", "consolidated1099"],
  ["partnership_k1s", "Partnership K-1s", "income", "k1"],
  ["mortgage", "Mortgage interest and property taxes", "home", "form1098"],
  ["health_insurance", "Health insurance", "health", "form1095c"],
  ["charitable", "Charitable contributions", "charitable", "donations"],
  ["estimated_tax", "Estimated tax payments", "other", "estimates"],
];

/** The nine rail categories, in the handoff's order. */
const CATEGORIES: readonly (readonly [string, string])[] = [
  ["personal", "Personal & Household Information"],
  ["income", "Income Sources"],
  ["home", "Home & Property"],
  ["health", "Health & Medical"],
  ["education", "Education & Student"],
  ["retirement", "Retirement"],
  ["charitable", "Charitable & Donations"],
  ["business", "Business & Self-Employment"],
  ["other", "Other Activity"],
];

/** Requests per category: the itemized rows; Personal & Household holds the binder's other done
 * requests, which the handoff never draws (21 − 7 = 14; their titles arrive with R-01-T11). */
function categoriesOf(rows: FeldRows): PortalCategoryOut[] {
  const itemized = GROUPS.length;
  return CATEGORIES.map(([code, label]) => {
    const own = GROUPS.filter(([, , c]) => c === code).map(([, , , key]) => rows[key]);
    const requested = code === "personal" ? FELD_BINDER.total - itemized : own.length;
    const complete =
      requested > 0 &&
      own.every((r) => r.client_status === "done" || r.client_status === "ignored");
    return { code, label, complete, requested };
  });
}

function groupsOf(rows: FeldRows): PortalGroupOut[] {
  return GROUPS.map(([code, label, category, key]) => ({
    code,
    label,
    category_code: category,
    rows: [rows[key]],
  }));
}

export const FELD_2025: PortalBinderRefOut = {
  id: FELD.binder,
  title: "2025 Binder",
  year: 2025,
  closed: false,
  read_only: false,
};
export const FELD_2024: PortalBinderRefOut = {
  id: FELD.binder2024,
  title: "2024 Binder (closed)",
  year: 2024,
  closed: true,
  read_only: true,
};

/** The binder from its rows: counts, ticks and the Mark as Done state are computed, never set. */
export function feldBinder(
  rows: FeldRows,
  options: { marked?: boolean; filter?: PortalBinderOut["filter"]; hideDone?: boolean } = {},
): PortalBinderOut {
  const itemized = Object.values(rows);
  const open = itemized.filter(
    (r) => r.client_status === "to_do" || r.client_status === "returned",
  ).length;
  const markDone: PortalBinderOut["mark_done"] = options.marked
    ? { state: "marked", marked_on: "2026-09-14", marked_by_name: "Claire Feld" }
    : { state: open > 0 ? "tonal" : "ready" };
  const groups = groupsOf(rows);
  return {
    binder: FELD_2025,
    layout: "groups",
    filter: options.filter ?? "requested",
    categories: categoriesOf(rows),
    groups: options.hideDone
      ? groups
          .map((g) => ({ ...g, rows: g.rows.filter((r) => r.client_status !== "done") }))
          .filter((g) => g.rows.length > 0)
      : groups,
    total: FELD_BINDER.total,
    done_count: FELD_BINDER.total - open,
    open_count: open,
    sorted_count: FELD_BINDER.sorted,
    mark_done: markDone,
    other_parties: [],
    allowed_actions: options.marked ? ["undo_mark_done"] : ["upload", "mark_done"],
  };
}

/** POR-03 a: two open requests (Intake 2); the estimated payments are uploading. */
export const FELD_ROWS_A: FeldRows = ROWS_A;

/** POR-03 c: Claire's 9:24 AM drop sorted both estimated-payment files onto their request. */
export const FELD_ROWS_C: FeldRows = {
  ...ROWS_A,
  estimates: {
    ...ROWS_A.estimates,
    client_status: "done",
    uploading_count: 0,
    files: [FELD_FILES.estimates, FELD_FILES.it2105],
    allowed_actions: ["withdraw", "comment"],
  },
};

/** POR-03 c2: the firm filed Claire's 9:12 AM email to the 1095-C (INB-02). */
export const FELD_ROWS_C2: FeldRows = {
  ...FELD_ROWS_C,
  form1095c: {
    ...ROWS_A.form1095c,
    client_status: "done",
    files: [FELD_FILES.emailed1095c],
    allowed_actions: ["comment"],
  },
};

/** POR-03 g (alternate path): Kevin Osei returned the 2024 form Claire uploaded. */
export const RETURNED_NOTE = {
  reason: "wrong_year",
  note: "This is the 2024 form. We need the 2025 Form 1095-C.",
  by_name: KEVIN,
  on: "2026-09-14",
} as const satisfies PortalRowOut["returned"];
export const FELD_ROWS_G: FeldRows = {
  ...ROWS_A,
  form1095c: {
    ...ROWS_A.form1095c,
    client_status: "returned",
    files: [FELD_FILES.returned1095c],
    returned: RETURNED_NOTE,
    allowed_actions: ["upload", "comment"],
  },
};

/** The closed 2024 binder in the picker: read-only. Its rows are not drawn in the handoff and
 * arrive with R-01-T11, so it opens empty. */
export function feldClosed2024(): PortalBinderOut {
  return {
    binder: FELD_2024,
    layout: "groups",
    filter: "requested",
    categories: [],
    groups: [],
    total: 0,
    done_count: 0,
    open_count: 0,
    sorted_count: 0,
    mark_done: { state: "tonal" },
    other_parties: [],
    allowed_actions: [],
  };
}

/** POR-03 h: nothing requested of Claire under "Requested". */
export function feldCaughtUp(): PortalBinderOut {
  return { ...feldBinder(FELD_ROWS_C2, { hideDone: true }), groups: [] };
}

/** POR-03 c, d: the drop batch's outcomes, polled by the screen. */
export const FELD_DROP: DropBatchOut = {
  batch_id: FELD.dropBatch,
  binder_id: FELD.binder,
  settled: true,
  files: [
    {
      file_id: FELD_FILES.estimates.id,
      file_name: FELD_FILES.estimates.name,
      outcome: "rule_linked",
      request_item_id: FELD.estimates,
    },
    {
      file_id: FELD_FILES.it2105.id,
      file_name: FELD_FILES.it2105.name,
      outcome: "rule_linked",
      request_item_id: FELD.estimates,
    },
    { file_id: FELD_FILES.scan.id, file_name: FELD_FILES.scan.name, outcome: "waiting" },
  ],
};

// --- POR-03 i: Dana Kowalski's own Northwind requests -----------------------------------------

const NORTHWIND_ENGAGEMENT = seed.engagementIds.northwind ?? id("engagement:northwind");
const danaRow = (
  key: string,
  title: string,
  status: PortalRowOut["client_status"],
  extra: Partial<PortalRowOut> = {},
): PortalRowOut => ({
  id: id(`northwind:${key}`),
  engagement_id: NORTHWIND_ENGAGEMENT,
  title,
  kind: "request",
  client_status: status,
  allowed_actions: status === "to_do" ? OPEN : ["comment"],
  ...extra,
});

/** Organisations Northwind's other requests are delegated to, as the note names them. */
export const NORTHWIND_OTHER_PARTIES = ["Keystone", "Harborline", "PayGrid", "Summit"] as const;

export function danaBinder(): PortalBinderOut {
  const bands: PortalBinderOut["bands"] = [
    {
      code: "census_payroll",
      label: "Census & Payroll",
      rows: [
        // "You uploaded Sep 2" (R-01-T10): the band grammar draws the receipt, never the file's
        // name, so the file is named for its request.
        danaRow("census", "Employee census file — 2025", "done", {
          files: [
            {
              id: id("file:northwind-census-2025"),
              name: "Employee census file — 2025.xlsx",
              receipt: { kind: "uploaded", on: "2026-09-02" },
              withdrawable: false,
            },
          ],
        }),
        danaRow("w3", "W-3 for 2025", "to_do", { due_on: "2026-09-18" }),
        danaRow("opt-out", "Opt-out elections — auto-enrolled employees", "to_do"),
        danaRow("pay-rates", "Pay rate authorizations", "to_do"),
      ],
    },
    {
      code: "plan_documents",
      label: "Plan documents",
      rows: [danaRow("opinion", "IRS opinion letter on the pre-approved plan document", "to_do")],
    },
    {
      code: "compliance",
      label: "Compliance",
      rows: [danaRow("complaints", "Participant complaints log and support", "to_do")],
    },
  ];
  const rows = bands.flatMap((b) => b.rows);
  const open = rows.filter((r) => r.client_status === "to_do").length;
  return {
    binder: {
      id: id("binder:northwind-py2025"),
      title: "PY2025 Audit requests",
      year: 2025,
      closed: false,
      read_only: false,
    },
    layout: "bands",
    filter: "requested",
    categories: [],
    bands,
    total: rows.length,
    done_count: rows.length - open,
    open_count: open,
    sorted_count: 0,
    mark_done: { state: "tonal" },
    other_parties: [...NORTHWIND_OTHER_PARTIES],
    allowed_actions: ["upload", "mark_done"],
  };
}

/** Dana's own requests are Northwind's 24 less the delegated ones (POR-01's delegations). */
export const DANA_OWN_REQUESTS = NORTHWIND_DELEGATIONS[0];

// --- POR-04: the 1095-C in the sheet ----------------------------------------------------------

const GUIDANCE_1095C =
  "Form 1095-C shows the health coverage Mercer Hill Health offered you each month of 2025. You don't attach it to your return, but we use it to confirm your coverage and that no premium tax credit needs to be repaid.";

export function sheet1095c(overrides: Partial<PortalRequestOut> = {}): PortalRequestOut {
  return {
    id: FELD.form1095c,
    engagement_id: FELD.engagement,
    binder_id: FELD.binder,
    variant: "request",
    category: { code: "health", label: "Health insurance" },
    title: "Form 1095-C From Mercer Hill Health",
    client_status: "to_do",
    requested_on: "2026-02-03",
    guidance: GUIDANCE_1095C,
    prior_year: { file_name: "Claire_Feld_2024_1095C_MercerHill.pdf", sent_on: "2025-03-03" },
    files: [],
    comment_count: 1,
    allowed_actions: OPEN,
    ...overrides,
  };
}

const comment = (
  key: string,
  itemId: string,
  author: { id: string; name: string; side: CommentOut["author_side"] },
  at: string,
  text: string,
): CommentOut => ({
  id: id(`comment:${key}`),
  request_item_id: itemId,
  author_user_id: author.id,
  author_name: author.name,
  author_side: author.side,
  created_at: at,
  text,
  visibility: "shared",
});

/** The shared threads the sheet and the room show (SPEC-032 comments). */
export const THREADS: Readonly<Record<string, CommentOut[]>> = {
  [FELD.form1095c]: [
    comment(
      "1095c-kevin",
      FELD.form1095c,
      { id: userId("kevin-osei"), name: KEVIN, side: "firm" },
      "2026-07-20T14:00:00Z",
      "Mercer Hill usually posts these in the employee portal by early March. A PDF download is perfect.",
    ),
  ],
};

// --- POR-04 e and f: the question and decision slots (fixture only; C-01, T-06 / T-09) --------

/** The `RequestSheet` question slot (docs/screens/POR-04.md, Variant-slot contract). */
export interface QuestionSlot {
  title: string;
  askedBy: string;
  context: readonly { label: string; value: string }[];
  note: string;
  options: readonly { code: string; label: string }[];
  selected: string;
  text: string;
  attachments: readonly { name: string; sizeBytes: number; done: boolean }[];
  answered?: { at: string; followUpBy: string };
}

export const SOUND_ELECTRIC_QUESTION: QuestionSlot = {
  title: "What was the $3,200 payment to Sound Electric?",
  askedBy: "Raj Malhotra",
  context: [
    { label: "Paid", value: "Aug 18, 2026 · check #2285" },
    { label: "From", value: "Front Range Bank ••4410" },
    { label: "Amount", value: "$3,200.00" },
    { label: "Recorded as", value: "Repairs & maintenance" },
  ],
  note: "Repairs were $640 in July, so we want to be sure this isn't new equipment.",
  options: [
    { code: "repair", label: "A repair or routine maintenance" },
    { code: "improvement", label: "New equipment or an improvement" },
    { code: "other", label: "Something else" },
  ],
  selected: "repair",
  text: "Two breakers failed on Aug 14; Sound Electric replaced them and rewired the espresso bar circuit. The panel was not replaced and nothing new was added.",
  attachments: [{ name: "SoundElectric_INV-SE-1187.pdf", sizeBytes: 188_000, done: true }],
};

/** The `RequestSheet` decision slot: figures are computed by code and handed to the sheet. */
export interface DecisionSlot {
  title: string;
  dueLabel: string;
  explanation: string;
  options: readonly { code: string; label: string }[];
  footnote: string;
}

/** Ridgeline §754 (POR-04 f): Pell Street II's 5 of 35 points of a $2,319,835 capital account,
 * bought for $360,000. Whole dollars, integer arithmetic: the pure function T-06 will own. */
export function section754(points: bigint, of: bigint, capital: bigint, price: bigint) {
  const share = (capital * points) / of;
  return { share, stepUp: price - share };
}
export const RIDGELINE_754 = section754(5n, 35n, 2_319_835n, 360_000n);

const usd = (n: bigint): string => `$${prose(n, "whole")}`;

export const RIDGELINE_DECISION: DecisionSlot = {
  title: "Should Ridgeline make a section 754 election for 2025?",
  dueLabel: "Answer by 5:00 PM CT today",
  explanation: `On June 30, 2025 Pell Street Ventures LLC sold 5 points to Pell Street II LLC for $360,000. Pell Street II's share of the partnership's basis in its property was ${usd(RIDGELINE_754.share)} — 5/35 of Pell Street Ventures' 6/30 capital of $2,319,835 (including $1,085 of first-half tax-exempt interest, per Reg. §1.704-1(b)(2)(iv)(l)). With a section 754 election, Pell Street II's share of that basis steps up by the ${usd(RIDGELINE_754.stepUp)} difference. The election is made by the partnership with a statement attached to its timely filed 2025 Form 1065 (extended due date September 15, 2026), and it also applies to all later transfers and distributions until revoked. Daniel Reyes recommends making the election.`,
  options: [
    { code: "yes", label: "Yes — make the election" },
    { code: "no", label: "No — don't make the election" },
    { code: "talk", label: "We'd like to talk first" },
  ],
  footnote:
    "If you choose yes, Brightwater Hale attaches the election statement to the return. The statement doesn't need a separate signature.",
};

// --- POR-14: the third-party rooms ------------------------------------------------------------

const roomRow = (
  key: string,
  title: string,
  state: PortalRoomRowOut["state"],
  on: string | null,
  extra: Partial<PortalRoomRowOut> = {},
): PortalRoomRowOut => ({
  id: id(`room:${key}`),
  engagement_id: NORTHWIND_ENGAGEMENT,
  title,
  state,
  state_on: on,
  disc: state === "due" || state === "returned" ? "ring" : "done",
  allowed_actions: state === "due" || state === "returned" ? ["upload", "comment"] : ["comment"],
  ...extra,
});

export const BRIDGE_GUIDANCE =
  "Your SOC 1 Type 2 report covers October 1, 2024 to September 30, 2025. Please upload a letter from Keystone management saying whether there were any material changes to the controls in that report, or any known control failures, from October 1 through December 31, 2025.";
export const BRIDGE_ID = id("room:bridge");

function keystoneBands(bridge: PortalRoomRowOut, allDone = false): PortalRoomOut["bands"] {
  const later = (key: string, title: string, due: string): PortalRoomRowOut =>
    allDone ? roomRow(key, title, "uploaded", null) : roomRow(key, title, "due", due);
  const recordkeeper = [
    roomRow(
      "balances",
      "Schedule of account balances — every participant, 12/31/2025",
      "uploaded",
      "2026-09-02",
    ),
    roomRow("loans", "Annual participant loan roll-forward — 2025", "uploaded", "2026-09-02"),
    roomRow(
      "brokerage",
      "BrokerWindow self-directed brokerage asset detail — 12/31/2025",
      "uploaded",
      "2026-09-02",
    ),
    later("withdrawals", "Withdrawals and distributions report — 2025", "2026-09-18"),
    later(
      "remittance",
      "Contribution remittance report — deposit date for each 2025 payroll",
      "2026-09-18",
    ),
  ];
  const soc = [
    roomRow("soc1", "SOC 1 Type 2 report — Oct 1, 2024 to Sep 30, 2025", "uploaded", "2026-09-02"),
    bridge,
    later("fees", "ERISA 408(b)(2) fee disclosure", "2026-09-25"),
    later("invoices", "Plan expense invoices paid from plan assets — 2025", "2026-09-25"),
  ];
  const band = (code: string, label: string, rows: PortalRoomRowOut[]) => ({
    code,
    label,
    uploaded: rows.filter((r) => r.disc === "done").length,
    total: rows.length,
    rows,
  });
  return [
    band("recordkeeper_reports", "Recordkeeper reports", recordkeeper),
    band("soc1_fees", "SOC 1 & fees", soc),
  ];
}

function keystoneRoom(bridge: PortalRoomRowOut, allDone = false): PortalRoomOut {
  const bands = keystoneBands(bridge, allDone);
  const uploaded = bands.reduce((n, b) => n + b.uploaded, 0);
  const total = bands.reduce((n, b) => n + b.total, 0);
  return {
    engagement_label: "Northwind Robotics 401(k) Plan · 2025 audit",
    firm_name: "Brightwater Hale",
    organisation_name: "Keystone Retirement Services",
    intro:
      "Brightwater Hale LLP asked Keystone Retirement Services for these items. You can only see and upload to these requests.",
    uploaded_count: uploaded,
    total,
    complete: uploaded === total,
    bands,
  };
}

const bridgeDue = roomRow("bridge", "Bridge letter — Oct 1 to Dec 31, 2025", "due", "2026-09-25", {
  guidance: BRIDGE_GUIDANCE,
  comment_count: 2,
});

/** POR-14 a: 4 of 9, the bridge letter open (Mon Sep 14). */
export const KEYSTONE_A = keystoneRoom(bridgeDue);
/** POR-14 b: Sam uploaded the bridge letter on Tue Sep 22; nobody has accepted it. */
export const KEYSTONE_B = keystoneRoom({
  ...bridgeDue,
  state: "in_review",
  state_on: "2026-09-22",
  disc: "done",
  allowed_actions: ["comment"],
});
/** POR-14 c: Marcus Delaney returned it on Wed Sep 23 for the wrong period. */
export const KEYSTONE_C = keystoneRoom({
  ...bridgeDue,
  state: "returned",
  state_on: "2026-09-23",
  returned: {
    reason: "wrong_period",
    note: "This letter covers Jan–Jun 2025. We need Oct 1 to Dec 31, 2025.",
    by_name: "Marcus Delaney",
    on: "2026-09-23",
  },
});
/** POR-14 e: everything Brightwater Hale asked Keystone for is in (Mon Sep 28). */
export const KEYSTONE_E = keystoneRoom(
  {
    ...bridgeDue,
    state: "uploaded",
    state_on: "2026-09-22",
    disc: "done",
    allowed_actions: ["comment"],
  },
  true,
);

/** POR-14 d: Harborline Trust Company's certifications contact, Fri Sep 11. */
export const HARBORLINE_D: PortalRoomOut = {
  engagement_label: "Northwind Robotics 401(k) Plan · 2025 audit",
  firm_name: "Brightwater Hale",
  organisation_name: "Harborline Trust Company",
  intro:
    "Brightwater Hale LLP asked Harborline Trust Company for these items. You can only see and upload to these requests. Under ERISA section 103(a)(3)(C), Brightwater Hale relies on your certification of the plan's investment information.",
  uploaded_count: 1,
  total: 2,
  complete: false,
  bands: [
    {
      code: "custodian",
      label: "Custodian",
      uploaded: 1,
      total: 2,
      rows: [
        roomRow(
          "certification",
          "Certification of investment information — 12/31/2025, signed",
          "in_review",
          "2026-09-11",
          { allowed_actions: ["comment"] },
        ),
        roomRow("trust-statement", "Trust statement — 12/31/2025", "due", "2026-09-18"),
      ],
    },
  ],
};

export const ROOM_THREADS: Readonly<Record<string, CommentOut[]>> = {
  [BRIDGE_ID]: [
    comment(
      "bridge-marcus",
      BRIDGE_ID,
      { id: userId("marcus-delaney"), name: "Marcus Delaney", side: "firm" },
      "2026-09-01T15:00:00Z",
      "A signed PDF on Keystone letterhead is fine.",
    ),
    comment(
      "bridge-sam",
      BRIDGE_ID,
      { id: portalUser("sam-ortiz"), name: "Sam Ortiz", side: "client" },
      "2026-09-10T15:00:00Z",
      "Our compliance team issues bridge letters on the 20th — I'll upload it by Sep 22.",
    ),
  ],
};

/** POR-14's figures: Keystone holds POR-01's 9 delegated items. */
export const KEYSTONE_ITEMS = KEYSTONE_DELEGATED;
