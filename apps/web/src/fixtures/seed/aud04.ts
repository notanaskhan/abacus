// AUD-04 Audit program & workpaper, General Audit Planning › Service Organizations (A-04-T27): the
// A-04-T04 record for Northwind PY2025's planning paper, its three tabs and the C4 citations its
// cited cells open in SHL-07. Words verbatim from the handoff spec. Dev and test only.

import type { CitationV2Out, WorkpaperCellOut, WorkpaperRecordOut } from "@abacus/api-client";
import { stableId } from "./prng";

export const PLANNING_PAPER = stableId("workpaper:northwind:general_audit_planning");
export const PLANNING_REF = "EBP-110";

export type Aud04Variant = "a" | "b" | "c";
export type Aud04Tab = "service_organizations" | "linkage" | "approach";

const KEYSTONE_CITE = stableId("citation:northwind:gap:keystone");
const CARVE_OUT_CITES = [
  stableId("citation:northwind:gap:carve-out:soc1"),
  stableId("citation:northwind:gap:carve-out:ebp140"),
] as const;

type Row = readonly [section: string, row: string, col: string, text: string, cites: string[]];

const SO: readonly Row[] = [
  [
    "organizations",
    "procedure",
    "value",
    "BH-EBP-110 step 4. Identified the organizations that process plan transactions and assessed whether each is relevant to the plan's financial statements.",
    [],
  ],
  [
    "organizations",
    "result",
    "value",
    "The plan uses four service organizations; three are relevant to the financial statements.",
    [],
  ],
  ["organizations", "org_1", "organization", "Keystone Retirement Services", [KEYSTONE_CITE]],
  [
    "organizations",
    "org_1",
    "services",
    "Recordkeeping: participant accounts, loans, distributions",
    [],
  ],
  ["organizations", "org_1", "relevant", "Yes", []],
  ["organizations", "org_1", "soc", "SOC 1 Type 2 · Oct 1, 2024 – Sep 30, 2025", []],
  [
    "organizations",
    "org_1",
    "subservice",
    "Carve-out — Ridgeway Data Services (hosting)",
    [...CARVE_OUT_CITES],
  ],
  ["organizations", "org_2", "organization", "Harborline Trust Company", []],
  [
    "organizations",
    "org_2",
    "services",
    "Directed trustee and custody; certifies investment information",
    [],
  ],
  ["organizations", "org_2", "relevant", "Yes", []],
  ["organizations", "org_2", "soc", "Certification under 29 CFR 2520.103-5", []],
  ["organizations", "org_2", "subservice", "—", []],
  ["organizations", "org_3", "organization", "PayGrid Payroll", []],
  ["organizations", "org_3", "services", "Payroll processing and deferral withholding", []],
  ["organizations", "org_3", "relevant", "Yes", []],
  [
    "organizations",
    "org_3",
    "soc",
    "No SOC 1 obtained — payroll inputs tested directly (BH-EBP-410)",
    [],
  ],
  ["organizations", "org_3", "subservice", "—", []],
  ["organizations", "org_4", "organization", "Summit Plan Administrators", []],
  ["organizations", "org_4", "services", "TPA: compliance testing and Form 5500 preparation", []],
  ["organizations", "org_4", "relevant", "No", []],
  ["organizations", "org_4", "soc", "—", []],
  ["organizations", "org_4", "subservice", "—", []],
  ["organizations", "ebp_140_required", "value", "Yes", []],
  [
    "organizations",
    "bridge_letter",
    "value",
    "Yes — Oct 1 – Dec 31, 2025 not covered (requested from Keystone Sep 1)",
    [],
  ],
  [
    "changes",
    "procedure",
    "value",
    "BH-EBP-110 step 5. Read the 2024 adoption agreement amendment and the PY2024 audit file.",
    [],
  ],
  [
    "changes",
    "amendments",
    "value",
    "Amendment effective Jan 1, 2025 added QACA automatic escalation of 1% a year to 15%.",
    [],
  ],
  ["changes", "prior_findings", "value", "None reported for PY2024.", []],
  ["changes", "mergers", "value", "None.", []],
]; // fmt: skip

const LINKAGE: readonly Row[] = [
  ["linkage", "org_1", "organization", "Keystone Retirement Services", []],
  ["linkage", "org_1", "procedure", "BH-EBP-140 steps 1–8", []],
  ["linkage", "org_1", "workpaper", "SOC 1 Evaluation", []],
  ["linkage", "org_2", "organization", "Harborline Trust Company", []],
  ["linkage", "org_2", "procedure", "BH-EBP-310 step 2", []],
  ["linkage", "org_2", "workpaper", "Investments & certification", []],
  ["linkage", "org_3", "organization", "PayGrid Payroll", []],
  ["linkage", "org_3", "procedure", "BH-EBP-410 steps 2–6", []],
  ["linkage", "org_3", "workpaper", "Contributions", []],
  ["linkage", "org_4", "organization", "Summit Plan Administrators", []],
  ["linkage", "org_4", "procedure", "None needed", []],
  ["linkage", "org_4", "workpaper", "—", []],
]; // fmt: skip

const APPROACH: readonly Row[] = [
  ["approach", "keystone", "value", "Yes, with bridge letter and CUEC testing", []],
  ["approach", "paygrid", "value", "No — substantive", []],
  ["approach", "harborline", "value", "certification relied on per §103(a)(3)(C)", []],
]; // fmt: skip

const ROWS: Record<Aud04Tab, readonly Row[]> = {
  service_organizations: SO,
  linkage: LINKAGE,
  approach: APPROACH,
};

const SECTIONS: Record<Aud04Tab, WorkpaperRecordOut["sections"]> = {
  service_organizations: [
    {
      key: "organizations",
      title: "SECTION 1 — SERVICE ORGANIZATIONS",
      band_kind: "section",
      sheet_key: "main",
      state: "in_progress",
      waiting_on_request_ids: [],
    },
    {
      key: "changes",
      title: "SECTION 2 — PLAN CHANGES AND PRIOR-YEAR MATTERS",
      band_kind: "section",
      sheet_key: "main",
      state: "in_progress",
      waiting_on_request_ids: [],
    },
  ],
  linkage: [
    {
      key: "linkage",
      title: "LINKAGE",
      band_kind: "section",
      sheet_key: "linkage",
      state: "in_progress",
      waiting_on_request_ids: [],
    },
  ],
  approach: [
    {
      key: "approach",
      title: "AUDIT APPROACH",
      band_kind: "section",
      sheet_key: "approach",
      state: "in_progress",
      waiting_on_request_ids: [],
    },
  ],
};

function cell(
  tab: Aud04Tab,
  [section, row, col, text, cites]: Row,
  n: number,
  variant: Aud04Variant,
): WorkpaperCellOut {
  const drafted = variant === "a";
  return {
    sheet_key: tab === "service_organizations" ? "main" : tab,
    cell_key: `${col}:${row}:${String(n)}`,
    row_key: row,
    col_key: col,
    section_key: section,
    value: { t: "text", v: text },
    value_source: drafted ? "agent" : "human",
    value_state: drafted ? "suggested" : "human",
    citation_ids: cites,
    suggestion_id: drafted ? stableId(`suggestion:northwind:gap:${row}:${col}`) : null,
    tickmarks: [],
    updated_version_no: drafted ? 1 : 2,
  };
}

export function aud04Record(variant: Aud04Variant, tab: Aud04Tab): WorkpaperRecordOut {
  return {
    id: PLANNING_PAPER,
    code: PLANNING_REF,
    title: "General Audit Planning",
    kind: "general_audit_planning",
    audit_area: null,
    tab,
    version_no: variant === "a" ? 1 : 2,
    current_version_no: variant === "a" ? 1 : 2,
    content_hash: (variant === "a" ? "1" : "2").repeat(64),
    program_step_keys: ["BH-EBP-110.4"],
    sections: SECTIONS[tab],
    cells: ROWS[tab].map((r, n) => cell(tab, r, n, variant)),
    flags: [],
    sign_offs:
      variant === "a"
        ? []
        : [
            { level: "L1", initials: "MD", signed_at: "2026-09-14T14:10:00-05:00", stale: false },
            ...(variant === "c"
              ? [
                  {
                    level: "L2" as const,
                    initials: "HL",
                    signed_at: "2026-09-14T15:05:00-05:00",
                    stale: false,
                  },
                ]
              : []),
          ],
    allowed_actions: ["workpaper.edit", "workpaper.export", "sign_off.prepare", "sign_off.review"],
  };
}

function step(id: string, n: number, title: string, quote: string | null): CitationV2Out {
  return {
    id,
    n,
    kind: "methodology_step",
    title,
    loc: "",
    quote,
    // The handoff names these sources without their text: withheld, never invented.
    quote_state: quote === null ? "withheld" : "shown",
    value_text: null,
    match_id: null,
    state: "valid",
    verified: true,
    verification_reason: null,
    created_by: { kind: "agent", label: "Accrued Agent" },
    retrieved_at: "2026-09-14T13:20:00Z",
    used_in: 1,
    moved: null,
    allowed_actions: [],
    source: {
      type: "methodology_step",
      id,
      version: "3",
      evidence_version_id: null,
      page: null,
    },
  };
}

/** The cited cells' sources: Keystone cites BH-EBP-110 step 4; the carve-out two sources (d). */
export const AUD04_CITATIONS: readonly CitationV2Out[] = [
  step(
    KEYSTONE_CITE,
    1,
    "BH-EBP-110: General Planning Procedures",
    "4. Determine whether the plan uses service organizations whose services are relevant to the plan's financial statements and whose controls are significant to the plan's internal control. If any are, perform the procedures in BH-EBP-140 Service Organizations.",
  ),
  {
    ...step(CARVE_OUT_CITES[0], 2, "Keystone SOC 1 Type 2", null),
    kind: "document_text",
    loc: "p. 14, section III",
  },
  step(CARVE_OUT_CITES[1], 3, "BH-EBP-140: Service Organizations", null),
];
