// AUD-03 Source documents · PBC with viewer (A-01-T15; docs/screens/AUD-03.md): what the seven
// artboards read beyond the Source Documents aggregate of seed/audits-index.ts.
//
// - The two documents the viewer opens: the BrokerWindow asset detail (a, c, f: Gordon Whitfield's
//   holdings, SSNs masked) and Harborline's certification (b: page 1 / 5, the certification
//   sentence lit as the screening's verified citation). Pages are the synthetic page images; the
//   words are the regions' labels and the masked text projection, verbatim from the spec.
// - The screening aggregates: b's passed card (Sep 11) and c's flagged card (Sep 9) whose reason
//   is the flag's verified citation, verbatim from the original c note card.
// - The snapshots: Sep 9 (c, d: the matcher's 62% proposal held on Schedule of Account
//   Balances), late September (f: every request received) and Sep 21 (g: overdue derived).

import type {
  CitationV2Out,
  RequestOwedByOut,
  ScreeningCardOut,
  SourceDocumentRowOut,
  SourceDocumentsOut,
  ViewerManifestOut,
  ViewerPageOut,
  ViewerRegionOut,
} from "@abacus/api-client";
import { northwindVersionId } from "./audits-index";
import { stableId } from "./prng";
import { binderRowCard } from "./screening";
import type { SeededCitation, SeededDocument } from "./trust";

type Rect = [number, number, number, number];

export const BROKERWINDOW_TITLE = "Brokerage / SDBA asset detail — BrokerWindow";
export const CERTIFIED_TITLE = "Certified trust report (full year, signed)";
export const BALANCES_TITLE = "Schedule of Account Balances";
export const IRS_LETTER_TITLE = "IRS opinion letter on the pre-approved plan document";

export const BROKERWINDOW = northwindVersionId(BROKERWINDOW_TITLE);
export const CERTIFICATION = northwindVersionId(CERTIFIED_TITLE);
export const BROKERWINDOW_PATH = "initial-input/BrokerWindow Asset Detail 2025.pdf";
export const BROKERWINDOW_FILE = "BrokerWindow Asset Detail 2025.pdf";
const CERTIFICATION_FILE = "Harborline Certification PY2025 signed.pdf";

/** Gordon Whitfield's BrokerWindow holdings (a), verbatim: they foot to $214,380.50. */
export const WHITFIELD_HOLDINGS: readonly (readonly [string, string, string])[] = [
  ["AAPL — Apple Inc", "$75,033.18", "35%"],
  ["MSFT — Microsoft Corp", "$53,595.13", "25%"],
  ["VTI — Vanguard Total Stock Market ETF", "$42,876.10", "20%"],
  ["BND — Vanguard Total Bond Market ETF", "$42,876.09", "20%"],
];
export const WHITFIELD_ACCOUNT_VALUE = "$214,380.50";

const PAGE: Omit<ViewerPageOut, "n"> = {
  width_pt: 612,
  height_pt: 792,
  rotation: 0,
  image_w: 1240,
  image_h: 1605,
  text_layer: true,
  pii_scan: "done",
};

function manifest(
  id: string,
  file_name: string,
  extra: Partial<ViewerManifestOut> = {},
): ViewerManifestOut {
  return {
    evidence_version_id: id,
    file_name,
    media_type: "application/pdf",
    status: "ready",
    reason: null,
    kind: "pages",
    page_count: 5,
    truncated: false,
    pages: [1, 2, 3, 4, 5].map((n) => ({ ...PAGE, n })),
    pii_masks: [],
    derivation_id: null,
    allowed_actions: [],
    view: "images",
    ...extra,
  };
}

const matchOf = (version: string, page: number, rect: Rect): string =>
  `ev:${version}#p${String(page)}:${rect.map(String).join(",")}`;

function region(
  version: string,
  rect: Rect,
  label: string,
  citationId: string | null = null,
): ViewerRegionOut {
  return {
    match_id: matchOf(version, 1, rect),
    page: 1,
    rects: [rect],
    sheet: null,
    cell: null,
    citation_id: citationId,
    label,
  };
}

const holdingRect = (i: number): Rect => [60, 268 + i * 20, 552, 286 + i * 20];

/** The two masked SSNs on the BrokerWindow page (F-04-T25's fixed regions). */
export const BROKERWINDOW_MASKS = [
  {
    id: stableId("mask:northwind:brokerwindow:whitfield-ssn"),
    page: 1,
    rect: [60, 222, 150, 236] as Rect,
    kind: "ssn" as const,
    display: "•••-••-2281",
  },
  {
    id: stableId("mask:northwind:brokerwindow:tanaka-ssn"),
    page: 1,
    rect: [60, 392, 150, 406] as Rect,
    kind: "ssn" as const,
    display: "•••-••-6610",
  },
];

/** The 9xx fake the logged reveal returns for Gordon Whitfield's SSN (fixture only). */
export const WHITFIELD_SSN_REVEALED = "900-41-2281";

const CERT_SENTENCE: Rect = [60, 180, 552, 214];
const FLAG_HEADER: Rect = [60, 60, 552, 110];

function citation(
  id: string,
  version: string,
  file: string,
  rect: Rect,
  quote: string,
  retrieved: string,
): CitationV2Out {
  return {
    id,
    n: 1,
    kind: "document_text",
    title: file,
    loc: "p. 1",
    quote,
    quote_state: "shown",
    value_text: null,
    match_id: matchOf(version, 1, rect),
    state: "valid",
    verified: true,
    verification_reason: null,
    created_by: { kind: "agent", label: "Accrued Agent" },
    retrieved_at: retrieved,
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

/** b: the certification sentence the screening cited, lit purple in the viewer. */
export const CERTIFICATION_CITATION = citation(
  stableId("citation:northwind:certification:period"),
  CERTIFICATION,
  CERTIFICATION_FILE,
  CERT_SENTENCE,
  "…is complete and accurate as of December 31, 2025 and for the year then ended",
  "2026-09-11T15:02:00Z",
);

/** c: the flag's verified reason, verbatim from the spec's c note card. */
export const BROKERWINDOW_FLAG = citation(
  stableId("citation:northwind:brokerwindow:wrong-document"),
  BROKERWINDOW,
  BROKERWINDOW_FILE,
  FLAG_HEADER,
  "This file covers only the 31 participants in BrokerWindow; a schedule of account balances covers every participant.",
  "2026-09-09T15:02:00Z",
);

export const AUD03_CITATIONS: SeededCitation[] = [CERTIFICATION_CITATION, BROKERWINDOW_FLAG].map(
  (out) => ({
    anchor: { type: "screening_result", id: out.id, ref: "screening", section: null },
    out,
  }),
);

export const AUD03_DOCUMENTS: Record<string, SeededDocument> = {
  [BROKERWINDOW]: {
    face: "statement",
    manifest: manifest(BROKERWINDOW, BROKERWINDOW_FILE, {
      pii_masks: BROKERWINDOW_MASKS,
      allowed_actions: ["pii.reveal"],
    }),
    regions: [
      region(BROKERWINDOW, FLAG_HEADER, "BrokerWindow Asset Detail Report", BROKERWINDOW_FLAG.id),
      region(BROKERWINDOW, [60, 240, 552, 254], WHITFIELD_ACCOUNT_VALUE),
      ...WHITFIELD_HOLDINGS.map(([security, value], i) =>
        region(BROKERWINDOW, holdingRect(i), `${security} ${value}`),
      ),
    ],
    // DEC-369: what an offshore reader gets instead of the page, the SSNs as their tokens.
    text: [
      {
        page: 1,
        text: [
          "Keystone Retirement Services",
          "BrokerWindow Asset Detail Report",
          "Northwind Robotics 401(k) Plan",
          "As of December 31, 2025",
          "Participant: Gordon Whitfield",
          `SSN: •••-••-2281 · Account value: ${WHITFIELD_ACCOUNT_VALUE}`,
          "Security | Market value | % of account",
          ...WHITFIELD_HOLDINGS.map((row) => row.join(" | ")),
          "Participant: Mei Tanaka",
          "SSN: •••-••-6610 · Account value: $168,240.00",
        ].join("\n"),
        unread: false,
      },
    ],
  },
  [CERTIFICATION]: {
    face: "statement",
    manifest: manifest(CERTIFICATION, CERTIFICATION_FILE),
    regions: [
      region(
        CERTIFICATION,
        CERT_SENTENCE,
        "Harborline Trust Company — Certification of Investment Information",
        CERTIFICATION_CITATION.id,
      ),
    ],
  },
};

// ---- Screening aggregates ----------------------------------------------------------------------

const PERIOD = { start: "2025-01-01", end: "2025-12-31" } as const;

/** b: the certified trust report's two passed checks, "Evidence screening · Sep 11". */
export function certificationCard(itemId: string): ScreeningCardOut {
  return {
    ...binderRowCard(
      { id: itemId, title: CERTIFIED_TITLE, screening: "passed" },
      1,
      "2026-09-11T15:02:00Z",
      PERIOD,
    ),
    checks: [
      {
        key: "right_document",
        verdict: "pass",
        source: "model",
        answer_ref: itemId,
        citation_ids: [],
      },
      {
        key: "right_period",
        verdict: "pass",
        source: "code",
        answer_ref: itemId,
        citation_ids: [CERTIFICATION_CITATION.id],
      },
    ],
  };
}

/** c: the BrokerWindow detail proposed for Schedule of Account Balances, flagged Wrong document. */
export function balancesCard(itemId: string): ScreeningCardOut {
  const base = binderRowCard(
    { id: itemId, title: BALANCES_TITLE, screening: "flagged" },
    1,
    "2026-09-09T15:02:00Z",
    PERIOD,
  );
  return {
    ...base,
    files_answering: 0,
    checks: [
      {
        key: "right_document",
        verdict: "flag",
        source: "model",
        answer_ref: itemId,
        citation_ids: [BROKERWINDOW_FLAG.id],
      },
      {
        key: "right_period",
        verdict: "pass",
        source: "code",
        answer_ref: itemId,
        citation_ids: [],
      },
    ],
    file_flags: [
      {
        evidence_version_id: BROKERWINDOW,
        file_name: BROKERWINDOW_FILE,
        reason_code: "wrong_document",
        region_ref: BROKERWINDOW_FLAG.id,
      },
    ],
  };
}

/** Any other answered row: its file passed both checks when it arrived. */
export function passedCard(itemId: string, title: string, on: string): ScreeningCardOut {
  return binderRowCard({ id: itemId, title, screening: "passed" }, 1, `${on}T15:02:00Z`, PERIOD);
}

// ---- Snapshots ---------------------------------------------------------------------------------

const RANK: Readonly<Record<string, number>> = {
  uploaded: 0,
  returned: 1,
  requested: 1,
  received: 2,
};

/** Counts and "Missing first" order again after rows changed (a decision, a snapshot). */
export function recount(
  docs: SourceDocumentsOut,
  sort: "missing_first" | "received_first" = "missing_first",
): SourceDocumentsOut {
  const sign = sort === "missing_first" ? 1 : -1;
  const groups = (docs.groups ?? []).map((g) => {
    const rows = (g.rows ?? [])
      .map((row, i) => ({ row, i }))
      .sort((a, b) => sign * ((RANK[a.row.status] ?? 1) - (RANK[b.row.status] ?? 1)) || a.i - b.i)
      .map(({ row }) => row);
    return {
      ...g,
      rows,
      received: rows.filter((r) => r.status === "received").length,
      total: rows.length,
    };
  });
  const all = groups.filter((g) => g.counted !== false).flatMap((g) => g.rows);
  return {
    ...docs,
    groups,
    received: all.filter((r) => r.status === "received").length,
    total: all.length,
    needs_review: all.filter((r) => r.status === "uploaded").length,
    requested: all.filter((r) => r.status !== "received" && r.status !== "uploaded").length,
  };
}

function mapRows(
  docs: SourceDocumentsOut,
  edit: (row: SourceDocumentRowOut) => SourceDocumentRowOut,
): SourceDocumentsOut {
  return recount({
    ...docs,
    groups: (docs.groups ?? []).map((g) => ({ ...g, rows: (g.rows ?? []).map(edit) })),
  });
}

const HARBORLINE: RequestOwedByOut = {
  kind: "organisation",
  display: "Harborline Trust Company",
};

/** c, d (Wed Sep 9): the certified trust report not yet in; the matcher's 62% proposal of the
 * BrokerWindow detail held on Schedule of Account Balances (10 of 24). */
export function sep9(docs: SourceDocumentsOut): SourceDocumentsOut {
  return mapRows(docs, (row) => {
    if (row.title === CERTIFIED_TITLE) {
      return {
        ...row,
        status: "requested",
        due_on: "2026-09-18",
        owed_by: HARBORLINE,
        latest_upload: null,
        match_confidence: null,
        linked_count: null,
        screening: null,
      };
    }
    if (row.title === BALANCES_TITLE) {
      return {
        ...row,
        status: "uploaded",
        latest_upload: {
          evidence_version_id: BROKERWINDOW,
          path_label: BROKERWINDOW_PATH,
          uploaded_on: "2026-09-01",
          uploader_kind: "firm",
        },
        match_confidence: 62,
        linked_count: 1,
        screening: "flagged",
      };
    }
    return row;
  });
}

/** f (late September): every Northwind request received; the late files uploaded Sep 24 and
 * matched 97%, each under "client-upload/" in the request's own words (the cert report keeps its
 * Harborline path), as the f artboard reads. */
export function allReceived(docs: SourceDocumentsOut): SourceDocumentsOut {
  return mapRows(docs, (row) => {
    if (row.status === "received") return row;
    const path =
      row.latest_upload?.path_label ??
      `client-upload/${row.title.replace(/[—/-]/g, " ").replace(/\s+/g, " ").trim()}.pdf`;
    return {
      ...row,
      status: "received",
      overdue: false,
      owed_by: null,
      latest_upload: {
        evidence_version_id: northwindVersionId(row.title),
        path_label: path,
        uploaded_on: "2026-09-24",
        uploader_kind: "client",
      },
      match_confidence: 97,
      linked_count: 1,
      screening: "passed",
    };
  });
}

/** g (Mon Sep 21) and any clock: `overdue` derived from `due_on < today`, never stored. */
export function asOf(docs: SourceDocumentsOut, today: string): SourceDocumentsOut {
  return mapRows(docs, (row) => ({
    ...row,
    overdue: row.status === "requested" && row.due_on != null && row.due_on < today,
  }));
}

/** The reminder to Dana (DEC-421): BND-04 c's designed wording with Northwind's
 * facts in its slots; the server composes it from the firm's published Reminder template. */
export function danaReminder(open: number, overdue: number): string {
  const late = overdue > 0 ? `, ${String(overdue)} of them past the due date` : "";
  return (
    `Hi Dana, thank you for what you have sent so far. ${String(open)} items are still open for ` +
    `PY2025 Employee Benefit Plan Audit${late}. You can upload them in the portal. Marcus Delaney ` +
    "is your contact at Brightwater Hale."
  );
}
