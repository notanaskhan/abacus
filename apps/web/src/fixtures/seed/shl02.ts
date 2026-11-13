// P-02-T11 (TASK-7619; docs/screens/SHL-02.md; C15 v1): the "Go…" palette's results on the
// Brightwater Hale seed, one response per artboard. Words are the handoff's (SHL-02 spec.md and the
// R2 revision); statuses are C2 codes the screen turns into words through status.ts. a–e run on
// E0 (Mon Sep 14, 2026 9:24 AM CT), f–g on Mon Sep 28, 2026 9:10 AM CT (P-02 OQ-6). There is never
// a wall count: e is a without the walled rows (DEC-43, DF-14).
import type { SearchItemOut, SearchRecentsOut, SearchResultsOut } from "@abacus/api-client";
import { stableId } from "./prng";

export const SHL02_CLOCK = "2026-09-14T09:24:00-05:00";
export const SHL02_SEP28 = "2026-09-28T09:10:00-05:00";

const id = (key: string) => stableId(`search:${key}`);

function item(
  object_type: string,
  key: string,
  title: string,
  screen_id: string,
  params: Record<string, string>,
  extra: Partial<SearchItemOut> = {},
): SearchItemOut {
  return {
    object_type,
    object_id: id(key),
    title,
    context: null,
    status: null,
    target: { screen_id, params },
    match_ranges: [],
    ...extra,
  };
}

const ranges = (title: string, q: string): [number, number][] => {
  const at = title.toLowerCase().indexOf(q.toLowerCase());
  return at < 0 ? [] : [[at, at + q.length]];
};

// --- a: "feld" ---------------------------------------------------------------------------------

const FELD_CLIENT = item(
  "client",
  "feld-client",
  "Jonah & Claire Feld",
  "CLI-02",
  { clientId: id("feld-client") },
  { context: "Household · Brooklyn, NY · TY2025 Form 1040", match_ranges: [[14, 18]] },
);
const FELD_1040 = item(
  "tax_return",
  "feld-1040",
  "2025 Form 1040",
  "TAX-02",
  { returnId: id("feld-1040"), family: "1040" },
  { context: "Jonah & Claire Feld", status: { code: "in_review", context: "manager" } },
);
const RIDGELINE_1065 = item(
  "tax_return",
  "ridgeline-1065",
  "2025 Form 1065",
  "CLI-02",
  { clientId: id("ridgeline-client"), family: "1065" },
  {
    context: "Jonah Feld, limited partner 25%",
    status: { code: "in_review", context: "partner" },
  },
);
const FELD_BINDER = item(
  "binder",
  "feld-binder",
  "2025 Binder",
  "BND-02",
  { binderId: id("feld-binder") },
  { context: "2 open requests", status: { code: "published", context: null } },
);
const FELD_W2 = item(
  "document",
  "feld-w2",
  "Claire_Feld_2025_W2_MercerHill.pdf",
  "FIL-01",
  { itemId: id("feld-w2"), folder: `permanent:${id("feld-client")}` },
  {
    status: { code: "approved", context: null },
    match_ranges: ranges("Claire_Feld_2025_W2_MercerHill.pdf", "feld"),
  },
);
const FELD_INBOX = item(
  "inbox_thread",
  "feld-inbox",
  "Re: 2025 tax documents",
  "INB-01",
  { threadId: id("feld-inbox") },
  { context: "Claire Feld · 9:12 AM", status: { code: "waiting", context: null } },
);

export const SHL02_A: SearchResultsOut = {
  groups: [
    { group: "clients", items: [FELD_CLIENT], has_more: false },
    { group: "returns", items: [FELD_1040, RIDGELINE_1065], has_more: false },
    { group: "binders", items: [FELD_BINDER], has_more: false },
    { group: "files", items: [FELD_W2], has_more: false },
    { group: "inbox", items: [FELD_INBOX], has_more: false },
  ],
  suggestion: null,
  total_visible: 6,
};

/** e: a scenario-local wall on two Feld documents (the W-2 and the inbox thread): exactly a
 * without them, and nothing that counts or hints at what was left out. */
export const SHL02_E: SearchResultsOut = {
  groups: SHL02_A.groups.filter((g) => g.group !== "files" && g.group !== "inbox"),
  suggestion: null,
  total_visible: 4,
};

// --- b: nothing typed (Recent) -----------------------------------------------------------------

export const SHL02_B_RECENTS: SearchRecentsOut = {
  items: [
    item(
      "assurance",
      "northwind-ebp",
      "Northwind Robotics 401(k) Plan",
      "AUD-02",
      { auditId: id("northwind-ebp") },
      { context: "PY2025 EBP Audit", status: { code: "processing", context: null } },
    ),
    { ...RIDGELINE_1065, context: "Ridgeline Property Partners, LP" },
    item(
      "close",
      "copperleaf-close",
      "Copperleaf Coffee Roasters, Inc.",
      "CLS-02",
      { closeId: id("copperleaf-close") },
      {
        context: "Close · 2026-08 · 4 days past due",
        status: { code: "in_progress", context: null },
      },
    ),
    item(
      "workbench_session",
      "ty2025-season",
      "TY2025 season progress by office",
      "WB-01",
      { sessionId: id("ty2025-season") },
      { context: "Session", status: { code: "awaiting_answer", context: null } },
    ),
    item(
      "agent_definition",
      "season-progress-reporter",
      "Season Progress Reporter",
      "WB-06",
      { agentId: id("season-progress-reporter") },
      { context: "Agent · Next run Mon, Sep 21 · 9:00 AM CT" },
    ),
  ],
};

// --- c: ">" agent mode ---------------------------------------------------------------------------

const AGENTS: [string, string][] = [
  ["Return Review Packet", "Tax"],
  ["K-1 Reconciliation Workpaper", "Tax"],
  ["Missing Document Chaser", "Firm operations"],
  ["Season Progress Reporter", "Firm operations"],
  ["EBP Audit Workpapers", "Audit"],
  ["Bank Reconciliation", "CAS"],
];

export const SHL02_C: SearchResultsOut = {
  groups: [
    {
      group: "agents",
      items: AGENTS.map(([title, tag]) =>
        item(
          "agent_definition",
          `agent-${title}`,
          title,
          "WB-06",
          { agentId: id(`agent-${title}`) },
          {
            context: tag,
            status: { code: "installed", context: null },
          },
        ),
      ),
      has_more: false,
    },
  ],
  suggestion: null,
  total_visible: AGENTS.length,
};

// --- d: "pellstret" (no match, a suggestion) ------------------------------------------------------

export const SHL02_D: SearchResultsOut = {
  groups: [],
  suggestion: {
    title: "Pell Street II LLC",
    context: "partner in Ridgeline Property Partners, LP",
    target: { screen_id: "CLI-02", params: { clientId: id("pell-street") } },
  },
  total_visible: 0,
};

// --- f: "granite" (Mon Sep 28) -------------------------------------------------------------------

export const SHL02_F: SearchResultsOut = {
  groups: [
    {
      group: "clients",
      items: [
        item(
          "client",
          "granite-client",
          "Granite Peak Outdoor Supply, Inc.",
          "CLI-02",
          {
            clientId: id("granite-client"),
          },
          { context: "C corp · Denver", match_ranges: [[0, 7]] },
        ),
      ],
      has_more: false,
    },
    {
      group: "audits",
      items: [
        item(
          "assurance",
          "granite-fs",
          "FY2026 Financial Statement Audit",
          "AUD-02",
          {
            auditId: id("granite-fs"),
          },
          {
            context: "Granite Peak Outdoor Supply, Inc.",
            status: { code: "fieldwork", context: null },
          },
        ),
      ],
      has_more: false,
    },
    {
      group: "todos",
      items: [
        item(
          "todo",
          "granite-surl",
          "Re-request 2 SURL files",
          "SHL-17",
          { todoId: id("granite-surl") },
          {
            context: "Cole Hart · BH-FS-430",
            due_on: "2026-09-28",
            status: { code: "open", context: null },
          },
        ),
      ],
      has_more: false,
    },
  ],
  suggestion: null,
  total_visible: 3,
};

// --- g: "explain" (saved prompts, deferred to W-03) ------------------------------------------------

export const SHL02_G: SearchResultsOut = {
  groups: [
    {
      group: "saved_prompts",
      items: [
        item(
          "saved_prompt",
          "yoy-change",
          "Explain a year-over-year change with evidence",
          "WB-12",
          {
            promptId: id("yoy-change"),
          },
          { context: "Audit", tag: "firm", use_count: 41, match_ranges: [[0, 7]] },
        ),
        item(
          "saved_prompt",
          "client-question",
          "Draft a client question for an unexplained variance",
          "WB-12",
          {
            promptId: id("client-question"),
          },
          { context: "Audit", use_count: 33 },
        ),
      ],
      has_more: false,
    },
  ],
  suggestion: null,
  total_visible: 2,
};

/** The response for search text on the seed (the fixture handler's lookup). */
// --- "ridgeline" (P-02-T12: J13 step 4, J16 step 9) ---------------------------------------------
// Daniel Reyes's Monday: the client and its 1065. TXP-01 is `planned`, so the 1065 opens the client
// record (CLI-02) as the backend routes it (tax/search.py, ENTITY_RETURNS_TO_TXP01).

const RIDGELINE_CLIENT = item(
  "client",
  "ridgeline-client",
  "Ridgeline Property Partners, LP",
  "CLI-02",
  { clientId: id("ridgeline-client") },
  { match_ranges: [[0, 9]] },
);

export const SHL02_RIDGELINE: SearchResultsOut = {
  groups: [
    { group: "clients", items: [RIDGELINE_CLIENT], has_more: false },
    {
      group: "returns",
      items: [{ ...RIDGELINE_1065, context: "Ridgeline Property Partners, LP" }],
      has_more: false,
    },
  ],
  suggestion: null,
  total_visible: 2,
};

export function resultsFor(q: string, walled = false): SearchResultsOut {
  const key = q.trim().toLowerCase();
  if (key === "ridgeline") return SHL02_RIDGELINE;
  if (key === "feld") return walled ? SHL02_E : SHL02_A;
  if (key === "pellstret") return SHL02_D;
  if (key === "granite") return SHL02_F;
  if (key === "explain") return SHL02_G;
  return { groups: [], suggestion: null, total_visible: 0 };
}
