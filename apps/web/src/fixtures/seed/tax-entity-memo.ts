// TXP-01's reads in fixture mode (T-05-T59; TXP-01 handoff states A–D): the Ridgeline preparer
// memo on the seeded sections (fixtures/seed/tax/ridgeline.ts, TPL-10's), each cited section's
// source as the memo read carries it (DEC-4939), the partnership's general information and the
// approved memo's opportunities. Words and figures are the handoff's; nothing is composed here.
import type {
  WorkbookGeneralInformationOut,
  WorkbookMemoCitationOut,
  WorkbookMemoOut,
  WorkbookOpportunitiesOut,
} from "@abacus/api-client";
import { stableId } from "./prng";
import { GENERAL_INFORMATION, MEMO_SECTIONS, RIDGELINE } from "./tax";

export type MemoState = "adopted" | "drafting" | "approved" | "stale";

const MEMO_ID = stableId("preparer-memo:ridgeline-2025");
const RETURN_ID = stableId("work-item:ridgeline-2025-1065");
const SECTION_KEYS = [
  "overview",
  "structural_events",
  "book_to_tax",
  "depreciation",
  "states_ptet",
  "distributions",
  "open_items",
  "opportunities",
] as const;
// The rail row each marker's source is (TPL-10's citations: [1]–[5]).
const SOURCES: Readonly<Record<number, { title: string; key: string }>> = {
  1: { title: "Partnership agreement", key: "partners" },
  2: { title: "Pell Street transfer memo", key: "allocation" },
  3: { title: "2025P:Ridgeline:V2", key: "engineReturn" },
  4: { title: "Fixed asset register", key: "taxYear" },
  5: { title: "State apportionment workpaper", key: "extension" },
};

export function memoCitation(n: number): WorkbookMemoCitationOut {
  const s = SOURCES[n] ?? { title: `Source ${String(n)}`, key: "partners" };
  return {
    id: stableId(`memo-citation:ridgeline:${String(n)}`),
    n,
    title: s.title,
    loc: s.key,
    quote: GENERAL_INFORMATION.find((r) => r.key === s.key)?.value ?? "",
    match: s.key,
  };
}

export function ridgelineMemo(state: MemoState): WorkbookMemoOut {
  if (state === "drafting") {
    return {
      status: "drafting",
      sections: [],
      seen_hash: "",
      stale_fields: [],
      allowed_actions: [],
      memo_id: MEMO_ID,
      version: 0,
    };
  }
  return {
    status: state === "stale" ? "stale" : state,
    sections: MEMO_SECTIONS.map((s, i) => ({
      key: SECTION_KEYS[i] ?? `section_${String(i)}`,
      title: s.heading,
      body: [...s.paragraphs, ...(s.bullets ?? [])].join(" "),
      human_owned: false,
      version: 1,
      citations: s.cite === undefined ? [] : [memoCitation(s.cite)],
      citation_ids: s.cite === undefined ? [] : [memoCitation(s.cite).id],
    })),
    seen_hash: "sha256:ridgeline-memo-v1",
    stale_fields: state === "stale" ? ["Ending capital 6,860,000 → 6,866,200"] : [],
    allowed_actions:
      state === "adopted"
        ? ["tax_memo.edit", "tax_memo.draft", "tax_memo.approve"]
        : ["tax_memo.edit", "tax_memo.draft"],
    memo_id: MEMO_ID,
    version: 1,
  };
}

export const RIDGELINE_GENERAL: WorkbookGeneralInformationOut = {
  return_id: RETURN_ID,
  entity_name: RIDGELINE,
  form: "1065",
  tax_year: 2025,
  ein_last4: "0287",
  accounting_method: "Income-tax basis",
  preparer_name: "Olivia Brandt",
  reviewer_name: "Samuel Ito",
  signer_name: "Daniel Reyes",
};

export const RIDGELINE_OPPORTUNITIES: WorkbookOpportunitiesOut = {
  items: [
    { key: stableId("opportunity:ridgeline:cost-seg"), title: "Cost segregation study — Elm Street" },
    { key: stableId("opportunity:ridgeline:754"), title: "§754 election" },
    { key: stableId("opportunity:ridgeline:nyc-ptet"), title: "NYC PTET for TY2027" },
  ],
};
