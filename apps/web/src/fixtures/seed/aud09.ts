// AUD-09 Internal control & exceptions (A-04-T32): the A-04-T25 shapes for Northwind PY2025. The
// seven exceptions (Exceptions!B2:E8) and the five processes are verbatim from the handoff spec; D2's
// two citations are its state b footer; the failed run is KNW-03 f's (the one seeded failure,
// 9:58 AM, BH-EBP-140 step 8). Variant f is D2 concluded by Margaret Okonkwo and communicated
// (A-06 and A-07 records, read through before they register). Dev and test only.

import type {
  CitationV2Out,
  ControlExceptionOut,
  ListPageControlExceptionOut,
  ListPageProcessOut,
  ProcessOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export type Aud09Variant = "a" | "f";

type Row = readonly [
  number,
  string,
  string,
  ControlExceptionOut["proposed_severity"],
  ControlExceptionOut["coso_component"],
  string | null,
];

// row, matter, description, proposed severity (null: Exception for resolution), COSO, candidate
const ROWS: readonly Row[] = [
  [
    2,
    "Remittance of deferrals not monitored",
    "The Dec 26, 2025 payroll deferrals and match ($48,600) reached Harborline on Jan 9, 2026; no sponsor control compares pay dates to deposit dates.",
    "significant_deficiency",
    "control_activities",
    null,
  ],
  [
    3,
    "Year-end contribution cutoff not recorded",
    "The Dec 26, 2025 payroll ($48,600) is not recorded as contributions receivable at December 31, 2025.",
    null,
    null,
    "48600.00",
  ],
  [
    4,
    "Service organization reports not reviewed",
    "Northwind does not review Keystone's SOC 1 report; its period ends Sep 30, 2025 and no bridge letter covers Oct 1 – Dec 31, 2025.",
    "deficiency",
    "monitoring",
    null,
  ],
  [
    5,
    "Complementary user entity controls unsupported",
    "Evidence exists for 2 of the 6 CUECs in Keystone's SOC 1 report.",
    "deficiency",
    "control_activities",
    null,
  ],
  [
    6,
    "Auto-enrolled participants with no deferrals",
    "4 auto-enrolled employees have no deferrals and no opt-out election on file.",
    null,
    null,
    null,
  ],
  [
    7,
    "Loan offsets for terminated participants",
    "3 terminated participants' loans ($14,850) were offset at distribution; confirm they are reported as distributions on Schedule H.",
    null,
    null,
    null,
  ],
  [
    8,
    "Census changes not reviewed",
    "No documented review of hires, terminations and pay changes sent to Keystone.",
    "deficiency",
    "information_communication",
    null,
  ],
];

const ACTIONS: ControlExceptionOut["allowed_actions"] = [
  "control.edit",
  "deficiency.propose_severity",
  "exception.route",
];

export const AUD09_CITATIONS: readonly CitationV2Out[] = [
  cell(
    stableId("citation:aud09:d2:paygrid"),
    1,
    "PayGrid Contribution Detail 2025.xlsx",
    "pay date 12/26/2025",
  ),
  cell(
    stableId("citation:aud09:d2:keystone"),
    2,
    "Keystone Account Balances PY2025.xlsx",
    "deposit 1/9/2026",
  ),
];

function cell(id: string, n: number, title: string, quote: string): CitationV2Out {
  return {
    id,
    n,
    kind: "sheet_cell",
    title,
    loc: "",
    quote,
    quote_state: "shown",
    value_text: null,
    match_id: null,
    state: "valid",
    verified: true,
    verification_reason: null,
    created_by: { kind: "agent", label: "Accrued Agent" },
    retrieved_at: "2026-09-14T17:20:00Z",
    used_in: 1,
    moved: null,
    allowed_actions: [],
    source: { type: "evidence_version", id, version: "1", evidence_version_id: id, page: null },
  };
}

export function aud09Exceptions(variant: Aud09Variant = "a"): ListPageControlExceptionOut {
  const items = ROWS.map(([row, matter, description, proposed, coso, candidate]) => {
    const concluded = variant === "f" && row === 2;
    return {
      address: `Exceptions!B${String(row)}`,
      sheet_row: row,
      matter,
      description,
      proposed_severity: proposed,
      concluded_severity: concluded ? ("significant_deficiency" as const) : null,
      coso_component: coso,
      disposition:
        proposed === null ? ("exception_for_resolution" as const) : ("proposed" as const),
      misstatement_candidate_amount: candidate,
      routed_kind: concluded ? ("finding" as const) : null,
      routed_ref: concluded ? "F-01" : null,
      citation_ids: row === 2 ? AUD09_CITATIONS.map((c) => c.id) : [],
      allowed_actions: variant === "f" ? [] : ACTIONS,
      suggestion_id: null,
    };
  });
  return { items, total: items.length };
}

// process, walkthrough (ISO), design, implementation, reliance, via SOC 1
const PROCESSES: readonly (readonly [
  string,
  string | null,
  ProcessOut["design"],
  ProcessOut["implementation"],
  ProcessOut["reliance"],
  boolean,
])[] = [
  ["Contributions & remittance", "2026-09-09", "deficient", "implemented", "none", false],
  ["Distributions", "2026-09-09", "effective", "implemented", "none", false],
  ["Loans", "2026-09-09", "effective", "implemented", "none", false],
  ["Participant data changes", "2026-09-10", "deficient", "not_implemented", "none", false],
  ["Investment elections", null, "not_assessed", "not_assessed", "via_soc1", true],
];

export const AUD09_KEYSTONE = stableId("service-org:northwind:keystone");

export function aud09Processes(): ListPageProcessOut {
  const items = PROCESSES.map(([name, on, design, implementation, reliance, soc], i) => ({
    id: stableId(`process:northwind:${String(i)}`),
    process_name: name,
    walkthrough_on: on,
    design,
    implementation,
    reliance,
    service_organization_id: soc ? AUD09_KEYSTONE : null,
    row_version: 1,
  }));
  return { items, total: items.length };
}
