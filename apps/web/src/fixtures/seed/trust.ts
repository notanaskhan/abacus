// The trust kit's fixture records (P-03-T07; C4 v1, docs/contracts/c04-citations-viewer.md; P-03
// §5.4): the citations SHL-07 reads and the seven scenario documents SHL-08 opens, typed with the
// generated C4 shapes. Copy and figures are the handoff's (SHL-07 and SHL-08 spec.md) and the seed's
// (blueprint 01 §9.4); nothing is ported from kit sample data. Page images are the synthetic
// grey-rule PNGs the E5 specimens use: no client bytes, no text layer. Regions sit at fixed
// page-point rects with match ids derived as the server derives them (C4 §3.1; INV-2).
//
// Footings (fixtures/trust.foot.test.ts):
//   Harborline funds 6,120,450.00 + 2,384,910.00 + 2,915,330.00 + 1,408,220.00 + 902,610.00
//     + 1,163,480.00 = 14,895,000.00; + BrokerWindow 1,605,000.00 = 16,500,000.00;
//     + notes receivable 312,400.00 = 16,812,400.00 (net assets, unadjusted)
//   Ridgeline TB 4510 tax-exempt interest 6,200 × 25% = 1,550 (Jonah Feld's box 18A)

import type {
  CitationV2Out,
  PiiMaskOut,
  ViewerManifestOut,
  ViewerPageOut,
  ViewerRegionOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

/** Mon Sep 14, 2026, 9:24 AM CT: SHL-08 (E0). */
export const CLOCK_VIEWER = "2026-09-14T09:24:00-05:00";
/** Mon Sep 14, 2026, 9:41 AM CT: SHL-07, and SHL-08b on the trial balance. */
export const CLOCK_POPOVER = "2026-09-14T09:41:00-05:00";
/** Mon Sep 14, 2026, 2:30 PM CT: SHL-08h (revision R2, frames G and H). */
export const CLOCK_AFTERNOON = "2026-09-14T14:30:00-05:00";

type Rect = [number, number, number, number];

/** A citation as the list routes filter it: where it is used, and its C4 display. */
export interface SeededCitation {
  anchor: { type: string; id: string; ref: string; section: string | null };
  out: CitationV2Out;
}

/** One scenario document: its manifest, the regions its citations light, and its page face. */
export interface SeededDocument {
  manifest: ViewerManifestOut;
  regions: ViewerRegionOut[];
  face: "form" | "statement";
}

const at = (version: string, page: number, rect: Rect): string =>
  `ev:${version}#p${String(page)}:${rect.map(String).join(",")}`;

const PAGE: Omit<ViewerPageOut, "n"> = {
  width_pt: 612,
  height_pt: 792,
  rotation: 0,
  image_w: 1240,
  image_h: 1605,
  text_layer: true,
  pii_scan: "done",
};

function pages(count: number): ViewerPageOut[] {
  return Array.from({ length: count }, (_, i) => ({ ...PAGE, n: i + 1 }));
}

function manifest(
  id: string,
  file_name: string,
  count: number,
  extra: Partial<ViewerManifestOut> = {},
): ViewerManifestOut {
  return {
    evidence_version_id: id,
    file_name,
    media_type: "application/pdf",
    status: "ready",
    reason: null,
    kind: "pages",
    page_count: count,
    truncated: false,
    pages: pages(count),
    pii_masks: [],
    derivation_id: null,
    allowed_actions: [],
    ...extra,
  };
}

function region(
  version: string,
  page: number,
  rect: Rect,
  citation: string | null,
  label: string | null,
): ViewerRegionOut {
  return {
    match_id: at(version, page, rect),
    page,
    rects: [rect],
    sheet: null,
    cell: null,
    citation_id: citation,
    label,
  };
}

// --- People and records ---------------------------------------------------------------------

const HANNAH_AGENT = { kind: "agent", label: "Hannah Leclerc via Agent" } as const;
const SAMUEL_AGENT = { kind: "agent", label: "Samuel Ito via Agent" } as const;

/** The Northwind Service Organizations workpaper (AUD-04) and its Keystone cell. */
export const SERVICE_ORGS_WORKPAPER = stableId("workpaper:northwind:service-organizations");
export const KEYSTONE_CELL = "SO!A1";
export const SERVICE_ORGS_SECTION = "service-organizations";
/** The AUD-05 Risk Assessment narrative's guidance block. */
export const RISK_WORKPAPER = stableId("workpaper:northwind:risk-assessment");
export const RISK_GUIDANCE_REF = "RA!guidance";

const EBP_V3 = stableId("methodology-template-version:bh-ebp:3");
const EBP_V2 = stableId("methodology-template-version:bh-ebp:2");
export const KEYSTONE_SOC1 = stableId("evidence-version:northwind:keystone-soc1-type2");
export const NORTHWIND_SPD = stableId("evidence-version:northwind:spd-2025");
export const HARBORLINE = stableId("evidence-version:northwind:harborline-net-trust-assets");
export const K1_DRAFT = stableId("evidence-version:feld:ridgeline-k1-draft");
export const K1_STATEMENT = stableId("evidence-version:feld:ridgeline-k1-statement");
export const RIDGELINE_TB = stableId("evidence-version:ridgeline:tb-2025");
export const W2_CLAIRE = stableId("evidence-version:feld:w2-mercer-hill-claire");
export const HALVARD_1099 = stableId("evidence-version:feld:halvard-consolidated-1099");
export const K1_PROCESSING = stableId("evidence-version:feld:ridgeline-k1-draft-processing");

/** The Feld 2025 Form 1040 line 2a ("Tax-exempt interest 1,550") the K-1 drawer opens from. */
export const LINE_2A = stableId("tax-form-line:feld:2025:1040:2a");
/** The Northwind trial balance's Total investments row (AUD-06). */
export const TB_TOTAL_INVESTMENTS = stableId("tb-row:northwind:py2025:total-investments");

const STEP_4 =
  "4. Identify each service organization that processes plan transactions. Assess whether its services are part of the plan's information system relevant to financial reporting and whether its controls are significant to the plan's internal control. If any is, perform BH-EBP-140 Service Organizations.";
const RISK_GUIDANCE =
  "Presumed fraud risks: 1. Management override of controls — prepopulated as a mandatory significant risk at the financial-statement level (AU-C 240); it cannot be removed; respond with journal-entry testing and experienced staffing. 2. Improper revenue recognition — presumed unless rebutted with documented rationale; for a plan, this means its principal inflows: employer and participant contributions.";

const SOC1_RECT: Rect = [72, 210, 540, 246];
const SPD_RECT: Rect = [72, 388, 540, 404];

function citation(
  id: string,
  n: number,
  fields: Partial<CitationV2Out> & Pick<CitationV2Out, "kind" | "title" | "loc" | "source">,
): CitationV2Out {
  return {
    id,
    n,
    quote: null,
    quote_state: "shown",
    value_text: null,
    match_id: null,
    state: "valid",
    verified: true,
    verification_reason: null,
    created_by: HANNAH_AGENT,
    retrieved_at: "2026-09-14T14:24:00Z",
    used_in: 1,
    moved: null,
    allowed_actions: [],
    ...fields,
  };
}

const keystoneAnchor = {
  type: "workpaper",
  id: SERVICE_ORGS_WORKPAPER,
  ref: KEYSTONE_CELL,
  section: SERVICE_ORGS_SECTION,
};

/** SHL-07a: BH-EBP-110 step 4, the program step the Keystone cell satisfies. */
export const STEP_CITATION: CitationV2Out = citation(stableId("citation:aud04:keystone:1"), 1, {
  kind: "methodology_step",
  title: "BH-EBP-110: General Planning Procedures",
  loc: "Step 4",
  quote: STEP_4,
  match_id: `ms:bh-ebp-110.4@${EBP_V3}`,
  source: {
    type: "methodology_template_version",
    id: EBP_V3,
    version: "3",
    evidence_version_id: null,
    page: null,
  },
});

/** SHL-07b, 2 of 3: the Keystone SOC 1 Type 2 report, Section I, p. 3. */
export const SOC1_CITATION: CitationV2Out = citation(stableId("citation:aud04:keystone:2"), 2, {
  kind: "document_text",
  title: "Keystone SOC 1 Type 2 report, Oct 1 2024 – Sep 30 2025",
  loc: "Section I, p. 3",
  quote:
    "Keystone provides recordkeeping, loan administration and distribution processing for defined contribution plans.",
  match_id: at(KEYSTONE_SOC1, 3, SOC1_RECT),
  source: {
    type: "evidence_version",
    id: KEYSTONE_SOC1,
    version: "1",
    evidence_version_id: KEYSTONE_SOC1,
    page: 3,
  },
});

/** SHL-07b, 3 of 3: the Northwind SPD 2025, p. 14. */
export const SPD_CITATION: CitationV2Out = citation(stableId("citation:aud04:keystone:3"), 3, {
  kind: "document_text",
  title: "Northwind SPD 2025",
  loc: "p. 14",
  quote: "Keystone Retirement Services is the plan's recordkeeper.",
  match_id: at(NORTHWIND_SPD, 14, SPD_RECT),
  source: {
    type: "evidence_version",
    id: NORTHWIND_SPD,
    version: "1",
    evidence_version_id: NORTHWIND_SPD,
    page: 14,
  },
});

/** SHL-07c: the AUD-05 Risk Assessment guidance (firm program text, no footer). */
export const GUIDANCE_CITATION: CitationV2Out = citation(stableId("citation:aud05:guidance"), 1, {
  kind: "methodology_step",
  title: "Risk Assessment — overall risks and fraud",
  loc: "",
  quote: RISK_GUIDANCE,
  match_id: `ms:bh-ebp-210.guidance@${EBP_V3}`,
  source: {
    type: "methodology_template_version",
    id: EBP_V3,
    version: "3",
    evidence_version_id: null,
    page: null,
  },
});

/** SHL-07e: the same step cited on EBP v2, superseded by EBP v3 on Jan 1, 2026. */
export const MOVED_CITATION: CitationV2Out = {
  ...STEP_CITATION,
  id: stableId("citation:aud04:keystone:moved"),
  match_id: `ms:bh-ebp-110.4@${EBP_V2}`,
  source: { ...STEP_CITATION.source, id: EBP_V2, version: "2" },
  state: "moved",
  moved: { successor_ref: "EBP v3", at: "2026-01-01T06:00:00Z" },
  allowed_actions: ["citation.relink"],
};

export const SHL07: Record<"single" | "stack" | "guidance" | "moved", SeededCitation[]> = {
  single: [{ anchor: keystoneAnchor, out: STEP_CITATION }],
  stack: [
    { anchor: keystoneAnchor, out: STEP_CITATION },
    { anchor: keystoneAnchor, out: SOC1_CITATION },
    { anchor: keystoneAnchor, out: SPD_CITATION },
  ],
  guidance: [
    {
      anchor: { type: "workpaper", id: RISK_WORKPAPER, ref: RISK_GUIDANCE_REF, section: "risk" },
      out: GUIDANCE_CITATION,
    },
  ],
  moved: [{ anchor: keystoneAnchor, out: MOVED_CITATION }],
};

/** The Service Organizations table the popover sits on (AUD-04; the Northwind seed parties). */
export const SERVICE_ORGANIZATIONS: readonly (readonly [string, string, "Yes" | "No"])[] = [
  ["Keystone Retirement Services", "Recordkeeping, participant accounts and loans", "Yes"],
  ["Harborline Trust Company", "Directed trustee and custodian; certifies investments", "Yes"],
  ["PayGrid Payroll", "Payroll processing and deferral remittance", "Yes"],
  ["Summit Plan Administrators", "TPA; prepares Form 5500 and Schedule H", "No"],
];

// --- SHL-08: the Feld K-1 (a, f), Harborline (b, h), Claire's W-2 (c), Halvard (d) -----------

const BOX_2: Rect = [372, 420, 568, 440];
const BOX_5: Rect = [372, 478, 568, 498];
const BOX_18A: Rect = [372, 612, 568, 632];
const STMT_18A: Rect = [54, 300, 558, 336];
const TB_4510: Rect = [54, 404, 558, 420];

function k1Citation(
  key: string,
  n: number,
  version: string,
  page: number,
  rect: Rect,
  title: string,
  loc: string,
  value: string,
): CitationV2Out {
  return citation(stableId(`citation:feld:1040:2a:${key}`), n, {
    kind: "document_text",
    title,
    loc,
    value_text: value,
    match_id: at(version, page, rect),
    created_by: SAMUEL_AGENT,
    source: {
      type: "evidence_version",
      id: version,
      version: "1",
      evidence_version_id: version,
      page,
    },
  });
}

/** The stack behind "Tax-exempt interest 1,550": the draft K-1, its statement, the TB. */
export const K1_STACK: CitationV2Out[] = [
  k1Citation(
    "k1",
    1,
    K1_DRAFT,
    1,
    BOX_18A,
    "Ridgeline_2025_K1_JonahFeld_DRAFT.pdf",
    "p. 1 · Box 18A",
    "1,550",
  ),
  k1Citation(
    "statement",
    2,
    K1_STATEMENT,
    3,
    STMT_18A,
    "Ridgeline 2025 K-1 statement",
    "p. 3",
    "1,550",
  ),
  k1Citation(
    "tb",
    3,
    RIDGELINE_TB,
    1,
    TB_4510,
    "Ridgeline TB 4510",
    "Tax-exempt interest",
    "6,200",
  ),
];

/** The linked-figure rows: the K-1's verified figures, by `value_text` (SHL-08a). */
export const K1_FIGURES: CitationV2Out[] = [
  k1Citation(
    "box2",
    4,
    K1_DRAFT,
    1,
    BOX_2,
    "Net rental real estate income (box 2)",
    "Box 2",
    "307,900",
  ),
  k1Citation("box5", 5, K1_DRAFT, 1, BOX_5, "Interest income (box 5)", "Box 5", "4,600"),
  { ...(K1_STACK[0] as CitationV2Out), title: "Tax-exempt interest income (box 18A)" },
];

const K1_MASKS: PiiMaskOut[] = [
  {
    id: stableId("mask:k1:ein"),
    page: 1,
    rect: [92, 118, 220, 134],
    kind: "ein",
    display: "••-•••0287",
  },
  {
    id: stableId("mask:k1:partner-ssn"),
    page: 1,
    rect: [92, 236, 220, 252],
    kind: "ssn",
    display: "•••-••-4417",
  },
];

/** The Harborline statement's fund rows on page 2 of 3 and where they sit. */
export const HARBORLINE_ROWS: readonly (readonly [string, string])[] = [
  ["KRS 500 Index Fund", "6,120,450.00"],
  ["KRS Target 2035 Fund", "2,384,910.00"],
  ["KRS Target 2045 Fund", "2,915,330.00"],
  ["KRS Bond Index Fund", "1,408,220.00"],
  ["KRS International Index Fund", "902,610.00"],
  ["Harborline Stable Value Fund", "1,163,480.00"],
  ["Subtotal mutual funds & CITs", "14,895,000.00"],
  ["BrokerWindow SDBA", "1,605,000.00"],
  ["TOTAL INVESTMENTS", "16,500,000.00"],
];

const rowRect = (i: number): Rect => [43, 196 + i * 20, 569, 212 + i * 20];

function harborlineCitation(i: number): CitationV2Out {
  const [name, value] = HARBORLINE_ROWS[i] ?? ["", ""];
  return citation(stableId(`citation:aud06:harborline:${String(i)}`), 1, {
    kind: "document_text",
    title: "Harborline Net Trust Assets 12-31-2025.pdf",
    loc: `p. 2 · ${name}`,
    value_text: value,
    match_id: at(HARBORLINE, 2, rowRect(i)),
    source: {
      type: "evidence_version",
      id: HARBORLINE,
      version: "1",
      evidence_version_id: HARBORLINE,
      page: 2,
    },
  });
}

/** Every Harborline row is cited by a trial-balance row; TOTAL INVESTMENTS is the lit one. */
export const HARBORLINE_CITATIONS: CitationV2Out[] = HARBORLINE_ROWS.map((_, i) =>
  harborlineCitation(i),
);
export const TOTAL_INVESTMENTS_CITATION = HARBORLINE_CITATIONS[8] as CitationV2Out;
export const HOVERED_2045 = HARBORLINE_CITATIONS[2] as CitationV2Out;

const W2_BOX_A: Rect = [60, 96, 252, 116];
const W2_BOX_1: Rect = [312, 96, 468, 116];
export const W2_WAGES = citation(stableId("citation:feld:1040:1a:w2-claire"), 1, {
  kind: "document_text",
  title: "2025 W-2 From Mercer Hill Health [Claire]",
  loc: "p. 1 · Box 1",
  value_text: "268,400.00",
  match_id: at(W2_CLAIRE, 1, W2_BOX_1),
  created_by: SAMUEL_AGENT,
  source: {
    type: "evidence_version",
    id: W2_CLAIRE,
    version: "1",
    evidence_version_id: W2_CLAIRE,
    page: 1,
  },
});

export const DOCUMENTS: Record<string, SeededDocument> = {
  [K1_DRAFT]: {
    face: "form",
    manifest: manifest(K1_DRAFT, "Ridgeline_2025_K1_JonahFeld_DRAFT.pdf", 3, {
      pii_masks: K1_MASKS,
      allowed_actions: ["pii.reveal"],
    }),
    regions: [
      region(K1_DRAFT, 1, BOX_18A, K1_STACK[0]?.id ?? null, "Form 1040 · line 2a 1,550"),
      region(K1_DRAFT, 1, BOX_2, K1_FIGURES[0]?.id ?? null, "307,900"),
      region(K1_DRAFT, 1, BOX_5, K1_FIGURES[1]?.id ?? null, "4,600"),
    ],
  },
  [K1_STATEMENT]: {
    face: "statement",
    manifest: manifest(K1_STATEMENT, "Ridgeline 2025 K-1 statement.pdf", 3),
    regions: [region(K1_STATEMENT, 3, STMT_18A, K1_STACK[1]?.id ?? null, "Box 18A 1,550")],
  },
  [RIDGELINE_TB]: {
    face: "statement",
    manifest: manifest(RIDGELINE_TB, "Ridgeline TB 2025.pdf", 1),
    regions: [region(RIDGELINE_TB, 1, TB_4510, K1_STACK[2]?.id ?? null, "4510 6,200")],
  },
  [HARBORLINE]: {
    face: "statement",
    manifest: manifest(HARBORLINE, "Harborline Net Trust Assets 12-31-2025.pdf", 3),
    regions: HARBORLINE_CITATIONS.map((c, i) =>
      region(HARBORLINE, 2, rowRect(i), c.id, HARBORLINE_ROWS[i]?.[1] ?? null),
    ),
  },
  [W2_CLAIRE]: {
    face: "form",
    manifest: manifest(W2_CLAIRE, "2025 W-2 From Mercer Hill Health [Claire].pdf", 1, {
      pii_masks: [
        {
          id: stableId("mask:w2:claire:ssn"),
          page: 1,
          rect: W2_BOX_A,
          kind: "ssn",
          display: "•••-••-6081",
        },
      ],
      allowed_actions: ["pii.reveal"],
    }),
    regions: [region(W2_CLAIRE, 1, W2_BOX_1, W2_WAGES.id, "268,400.00")],
  },
  [HALVARD_1099]: {
    face: "form",
    manifest: manifest(HALVARD_1099, "Halvard_2025_Consolidated_1099.pdf", 0, {
      status: "password_protected",
      reason: "encrypted",
      kind: "none",
      pages: [],
      allowed_actions: ["evidence.unlock"],
    }),
    regions: [],
  },
};

/** The trial balance's figures the Harborline total ties to (SHL-08b). */
export const NORTHWIND_TB_TIE = {
  totalInvestments: "16,500,000.00",
  notesReceivable: "312,400.00",
  netAssetsUnadjusted: "16,812,400.00",
} as const;

/** "Also cited" under the K-1 stack (SHL-08a). */
export const ALSO_CITED =
  "Also cited: Ridgeline statement p. 3 (municipal bond fund, 18A detail) · Ridgeline TB 4510 Tax-exempt interest 6,200 × 25% = 1,550.";
