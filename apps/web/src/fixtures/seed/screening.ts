// SHL-20 Evidence screening fixture records (P-06-T22; docs/screens/SHL-20.md; P-06 §5.4): the
// Granite Peak FY2026 SURL request's screening aggregates on the C5 v1.2 shapes, the two flag
// citations (verified, their reasons the handoff's §9.3.4 sentences, verbatim), the viewer
// documents "View" opens on, and the screening-return draft. Typed with the generated client.
//
// Figures (fixtures/screening.foot.test.ts):
//   a, b, f  Sat Sep 26: 31 files, 2 flagged, 29 answer (31 − 2 = 29)
//   c        Mon Sep 28: the 2 corrected files screening ("Screening 2 new files…")
//   d        Mon Sep 28: 40 of 40 payments supported
//   e        Fri Sep 25: FRF-30418.pdf filed from the Inbox, not linked: not screened

import type {
  CitationV2Out,
  FollowUpOut,
  ReasonCodeOut,
  ScreeningCardOut,
  ViewerManifestOut,
  ViewerRegionOut,
} from "@abacus/api-client";
import { getSeed } from "./index";
import { stableId } from "./prng";
import type { SeededDocument } from "./trust";

/** Sat Sep 26, 2026, 10:14 AM CT (a, f). */
export const CLOCK_FLAGGED = "2026-09-26T10:14:00-05:00";
/** Sat Sep 26, 2026, 10:16 AM CT (b; spec.md wins over the README's Sep 14). */
export const CLOCK_DRAFT = "2026-09-26T10:16:00-05:00";
/** Mon Sep 28, 2026, 9:05 AM CT (c, d). */
export const CLOCK_RERUN = "2026-09-28T09:05:00-05:00";
/** Fri Sep 25, 2026 (e: the handoff draws a date only; the time of day is the demo's 9:24 AM). */
export const CLOCK_UNLINKED = "2026-09-25T09:24:00-05:00";

const seed = getSeed();
export const GRANITE_PEAK = seed.engagementIds.A2 ?? "";
/** The SURL request SHL-14 f drafted (same id). */
export const SURL_ITEM = stableId("request:granite-peak:surl");
export const SURL_TITLE = "Support for 40 subsequent disbursements (SURL)";
export const SURL_PERIOD = { start: "2026-06-01", end: "2026-09-18" } as const;
export const LUIS_FERRANTE = "Luis Ferrante";
/** e's unlinked file. */
export const UNLINKED_FILE = "FRF-30418.pdf";

export const STATEMENT_VERSION = stableId("evidence-version:granite-peak:surl:granite-rock-aug");
export const INVOICE_VERSION = stableId("evidence-version:granite-peak:surl:invoice-40117");
export const STATEMENT_FILE = "Granite Rock Logistics — August statement.pdf";
export const INVOICE_FILE = "Invoice 40117.pdf";

type Rect = [number, number, number, number];
const STATEMENT_HEADER: Rect = [300, 72, 560, 96];
const INVOICE_REF: Rect = [54, 140, 320, 160];

const matchOf = (version: string, page: number, rect: Rect): string =>
  `ev:${version}#p${String(page)}:${rect.map(String).join(",")}`;

function flagCitation(
  key: string,
  version: string,
  file: string,
  rect: Rect,
  reason: string,
): CitationV2Out {
  return {
    id: stableId(`citation:granite-peak:surl:${key}`),
    n: 1,
    kind: "document_text",
    title: file,
    loc: "p. 1",
    quote: reason,
    quote_state: "shown",
    value_text: null,
    match_id: matchOf(version, 1, rect),
    state: "valid",
    verified: true,
    verification_reason: null,
    created_by: { kind: "agent", label: "Accrued Agent" },
    retrieved_at: "2026-09-26T15:12:00Z",
    used_in: 1,
    moved: null,
    allowed_actions: [],
    source: {
      type: "evidence_version",
      id: version,
      version: "1",
      evidence_version_id: version,
      page: 1,
    },
  };
}

/** The two flags' verified citations: their reasons are §9.3.4's, verbatim. */
export const STATEMENT_FLAG = flagCitation(
  "statement",
  STATEMENT_VERSION,
  STATEMENT_FILE,
  STATEMENT_HEADER,
  "This is a statement, not the invoice for payment #40188 ($23,940).",
);
export const INVOICE_FLAG = flagCitation(
  "invoice",
  INVOICE_VERSION,
  INVOICE_FILE,
  INVOICE_REF,
  "The invoice matches payment #40171, not #40117.",
);

function manifest(id: string, name: string): ViewerManifestOut {
  return {
    evidence_version_id: id,
    file_name: name,
    media_type: "application/pdf",
    status: "ready",
    reason: null,
    kind: "pages",
    page_count: 2,
    truncated: false,
    pages: [1, 2].map((n) => ({
      n,
      width_pt: 612,
      height_pt: 792,
      rotation: 0 as const,
      image_w: 1240,
      image_h: 1605,
      text_layer: true,
      pii_scan: "done" as const,
    })),
    pii_masks: [],
    derivation_id: null,
    allowed_actions: [],
  };
}

function region(citation: CitationV2Out, rect: Rect, label: string): ViewerRegionOut {
  return {
    match_id: citation.match_id ?? "",
    page: 1,
    rects: [rect],
    sheet: null,
    cell: null,
    citation_id: citation.id,
    label,
  };
}

/** What "View" opens: each flagged file, its deciding region lit. */
export const FLAGGED_DOCUMENTS: Record<string, SeededDocument> = {
  [STATEMENT_VERSION]: {
    face: "statement",
    manifest: manifest(STATEMENT_VERSION, STATEMENT_FILE),
    regions: [region(STATEMENT_FLAG, STATEMENT_HEADER, "Statement — August 2026")],
  },
  [INVOICE_VERSION]: {
    face: "statement",
    manifest: manifest(INVOICE_VERSION, INVOICE_FILE),
    regions: [region(INVOICE_FLAG, INVOICE_REF, "Invoice 40117")],
  },
};

const PROVENANCE = { prompt_ref: "screener@v3", duration_ms: 2000 } as const;
const ACTIONS = ["screening.feedback", "screening.request"];

/** a, b, f: Sat Sep 26, screened 10:12 AM: 31 files, 2 flagged by the reviewer, period passes. */
export const FLAGGED_CARD: ScreeningCardOut = {
  request_item_id: SURL_ITEM,
  screening_result_id: stableId("screening:granite-peak:surl:1"),
  batch_no: 1,
  verdict: "flagged",
  running: false,
  files_total: 31,
  files_answering: 29,
  checks: [
    {
      key: "right_document",
      verdict: "flag",
      source: "model",
      answer_ref: SURL_ITEM,
      citation_ids: [STATEMENT_FLAG.id, INVOICE_FLAG.id],
    },
    {
      key: "right_period",
      verdict: "pass",
      source: "code",
      answer_ref: SURL_ITEM,
      citation_ids: [],
    },
  ],
  file_flags: [
    {
      evidence_version_id: STATEMENT_VERSION,
      file_name: STATEMENT_FILE,
      reason_code: "wrong_document",
      region_ref: STATEMENT_FLAG.id,
    },
    {
      evidence_version_id: INVOICE_VERSION,
      file_name: INVOICE_FILE,
      reason_code: "wrong_document",
      region_ref: INVOICE_FLAG.id,
    },
  ],
  provenance: { ...PROVENANCE, screened_at: "2026-09-26T15:12:00Z" },
  my_feedback: null,
  allowed_actions: ACTIONS,
  request_title: SURL_TITLE,
  period_start: SURL_PERIOD.start,
  period_end: SURL_PERIOD.end,
};

/** c: Mon Sep 28, the corrected files received; the rerun runs on the 2 not yet answering. */
export const RUNNING_CARD: ScreeningCardOut = {
  ...FLAGGED_CARD,
  running: true,
  allowed_actions: ["screening.feedback"],
};

/** d: the superseding aggregate: 40 of 40 payments supported, both checks pass. */
export const PASSED_CARD: ScreeningCardOut = {
  ...FLAGGED_CARD,
  screening_result_id: stableId("screening:granite-peak:surl:2"),
  batch_no: 2,
  verdict: "passed",
  files_total: 40,
  files_answering: 40,
  checks: [
    {
      key: "right_document",
      verdict: "pass",
      source: "model",
      answer_ref: SURL_ITEM,
      citation_ids: [],
    },
    {
      key: "right_period",
      verdict: "pass",
      source: "code",
      answer_ref: SURL_ITEM,
      citation_ids: [],
    },
  ],
  file_flags: [],
  provenance: { ...PROVENANCE, screened_at: "2026-09-28T14:05:00Z" },
};

/** The send-back catalogue (migrations 0015 and 0071: the platform's codes and labels). */
export const SEND_BACK_REASONS: ReasonCodeOut[] = [
  ["wrong_document", "Wrong document", "Not the document the request asks for."],
  ["wrong_year", "Wrong year", "A document for another year."],
  ["incomplete", "Incomplete", "Part of what was requested is missing."],
  ["illegible", "Illegible", "The evidence can't be read reliably."],
  [
    "does_not_agree",
    "Doesn't agree to the ledger",
    "Totals or balances don't agree to the general ledger.",
  ],
  ["unsigned", "Unsigned", "A required signature or approval is missing."],
  ["other", "Other", "Another reason, explained in the note."],
].map(([code = "", label = "", description = ""]) => ({
  code,
  label,
  description,
  requires_note: code === "other",
}));

/** b: the screening-return draft to Luis Ferrante, composed from the Return template's parts
 * (DV-1): the recipient's first name, the request title and each returning file with its reason
 * label, signed by the person drafting it. Never the handoff's per-payment model sentences. */
export function screeningReturnDraft(recipientUserId: string, signer: string): FollowUpOut {
  return {
    id: stableId("follow-up:granite-peak:surl:return"),
    engagement_id: GRANITE_PEAK,
    binder_id: null,
    kind: "screening_return",
    status: "drafted",
    recipient_user_id: recipientUserId,
    recipient_contact_id: null,
    recipient_name: LUIS_FERRANTE,
    items: [
      { request_item_id: SURL_ITEM, title: SURL_TITLE, due_on: "2026-10-02", overdue: false },
    ],
    subject: SURL_TITLE,
    body: [
      "Hi Luis,",
      "",
      SURL_TITLE,
      `${STATEMENT_FILE} · Wrong document`,
      `${INVOICE_FILE} · Wrong document`,
      "",
      signer,
    ].join("\n"),
    edited: false,
    drafted_by_kind: "agent",
    template_key: "notification.follow_up_sent.screening_return",
    created_at: "2026-09-26T15:16:00Z",
    sent_by: null,
    sent_at: null,
    undo_until: null,
    allowed_actions: ["follow_up.draft", "follow_up.send"],
  };
}

/** BND-02 (R2, g): a binder row's screening aggregate as the dock card reads it. Every screened
 * client upload in the Feld binder passes both checks; the estimates (g) were screened at 9:31 AM
 * against the four TY2025 installments, Apr 15, 2025 – Jan 15, 2026 (DV-2). */
export function binderRowCard(
  row: { id: string; title: string; screening?: ScreeningCardOut["verdict"] | null },
  files: number,
  screenedAt: string,
  period: { start: string; end: string } | null,
): ScreeningCardOut {
  const screened = row.screening != null && row.screening !== "not_screened";
  return {
    request_item_id: row.id,
    screening_result_id: screened ? stableId(`screening:${row.id}:1`) : null,
    batch_no: screened ? 1 : null,
    verdict: row.screening ?? "not_screened",
    running: false,
    files_total: files,
    files_answering: screened ? files : 0,
    checks: [
      {
        key: "right_document",
        verdict: screened ? "pass" : "not_run",
        source: "model",
        answer_ref: row.id,
        citation_ids: [],
      },
      {
        key: "right_period",
        verdict: screened ? "pass" : "not_run",
        source: "code",
        answer_ref: row.id,
        citation_ids: [],
      },
    ],
    file_flags: [],
    provenance: screened
      ? { ...PROVENANCE, screened_at: screenedAt }
      : { prompt_ref: null, duration_ms: null, screened_at: null },
    my_feedback: null,
    allowed_actions: screened ? ACTIONS : ["screening.request"],
    request_title: row.title,
    period_start: period?.start ?? null,
    period_end: period?.end ?? null,
  };
}

/** g: the estimates' expected period, the four TY2025 installments. */
export const ESTIMATES_PERIOD = { start: "2025-04-15", end: "2026-01-15" } as const;
