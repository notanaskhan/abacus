// TXT-01's fixture records (T-07-T15; T-07 §5.3; SPEC-656 AC-1.1 to AC-5.2): the Calloway Family
// Trust's governing instrument, its clause tree, the masked text of the reader's page and the read
// models of each artboard, typed with the generated FW-1 shapes (T-07-T05). Copy and figures are
// the handoff's (TXT-01 spec.md); nothing is ported from kit sample data and nothing is summed
// here (the read model's figures are the engine's, T-07-T09). No clause text is stored server-side:
// the reader re-reads the masked text projection (`GET /v1/evidence-versions/{v}/text`).
import type {
  InstrumentClausesOut,
  InstrumentDeterminationOut,
  InstrumentOut,
  ViewerTextOut,
} from "@abacus/api-client";
import { CALLOWAY_TRUST, FIDUCIARY_IDS } from "./fiduciary";
import { stableId } from "./prng";

export const AGREEMENT_FILE = "Calloway_Family_Trust_Agreement_2011.pdf";
export const AGREEMENT_PAGES = 11;
export const READER_PAGE = 4;

export const INSTRUMENT_IDS = {
  entity: stableId("client_entity:calloway-family-trust"),
  instrument: stableId("governing_instrument:calloway:2011"),
  version: stableId("evidence_version:calloway-agreement-2011"),
  segmentation: stableId("instrument_segmentation:calloway:1"),
  interpretation: stableId("instrument_interpretation:calloway:2025"),
  run: stableId("agent_run:calloway:instrument-reader:1"),
} as const;

const HASH = "0".repeat(64);
const clauseId = (label: string) => stableId(`instrument_clause:calloway:${label}`);
const citationId = (label: string, key: string) => stableId(`citation:calloway:${key}:${label}`);

// The clause tree (labels, pages, regions): ids and boxes only, never text (AC-15.3).
const TREE: [
  label: string,
  heading: string | null,
  from: number,
  to: number,
  parent: string | null,
][] = [
  ["Art. I", null, 3, 4, null],
  ["Art. II", "DEFINITIONS", 4, 4, null],
  ["Art. III", "DISTRIBUTIONS DURING THE TRUST TERM", 4, 4, null],
  ["Art. III(a)", null, 4, 4, "Art. III"],
  ["Art. III(b)", null, 4, 4, "Art. III"],
  ["Art. IV", "ACCUMULATION AND PRINCIPAL", 4, 4, null],
  ["Art. IV(a)", null, 4, 4, "Art. IV"],
  ["Art. IV(b)", null, 4, 4, "Art. IV"],
  ["Art. V", "THE TRUSTEE", 4, 4, null],
  ["Art. V(c)", null, 4, 4, "Art. V"],
];

export function callowayClauses(): InstrumentClausesOut {
  return {
    instrument_id: INSTRUMENT_IDS.instrument,
    segmentation_id: INSTRUMENT_IDS.segmentation,
    status: "segmented",
    clauses: TREE.map(([label, heading, from, to, parent], i) => ({
      id: clauseId(label),
      label,
      heading,
      ordinal: i,
      parent_clause_id: parent === null ? null : clauseId(parent),
      page_from: from,
      page_to: to,
      regions: [{ page: to, bbox: [52, 40 + i * 60, 708, 92 + i * 60] }],
      text_sha256: HASH,
    })),
  };
}

// Page 4 as the masked text projection returns it (TXT-01 spec "Visible text (page 4)").
const PAGE_4 = [
  "…and the Trustee accepts the trust and agrees to administer it under the terms of this Agreement.",
  "ARTICLE II — DEFINITIONS",
  'For purposes of this Agreement: the term "Trustee" includes the named Trustee and every successor then serving; the term "Code" means the Internal Revenue Code of 1986, as amended; and the term "net income" means the income of the trust determined under the Illinois Principal and Income Act, as amended from time to time, after payment of expenses properly chargeable to income. Gains from the sale or exchange of trust assets shall be allocated to principal.',
  "ARTICLE III — DISTRIBUTIONS DURING THE TRUST TERM",
  "(a) During the trust term the Trustee may distribute to or for the benefit of the Settlor's grandchildren, NORA CALLOWAY and THEO CALLOWAY, so much of the net income as the Trustee in the Trustee's discretion determines, in equal or unequal shares, and need not distribute income to either beneficiary in any year.",
  "(b) The trust term ends when the younger living grandchild reaches age thirty-five. The Trustee shall then distribute the remaining principal and any undistributed income to the Settlor's then living descendants, per stirpes.",
  "ARTICLE IV — ACCUMULATION AND PRINCIPAL",
  "(a) Any net income not distributed in a calendar year shall be accumulated and added to principal at the end of that year.",
  "(b) The Trustee may distribute principal to or for the benefit of either grandchild as the Trustee determines necessary for that beneficiary's health, education, maintenance and support, taking into account other resources known to the Trustee.",
  "ARTICLE V — THE TRUSTEE",
  "(c) The Trustee shall be entitled to reasonable compensation, which shall be charged against principal.",
].join("\n");

export function callowayText(): ViewerTextOut {
  return {
    items: [{ page: READER_PAGE, text: PAGE_4, unread: false }],
    sheets: [],
    truncated: false,
  };
}

type Row = [key: InstrumentDeterminationOut["key"], code: string, text: string, clauses: string[]];
const ROWS: Row[] = [
  [
    "grantor_status",
    "non_grantor",
    "Non-grantor: no retained powers under §§673–677; settlor deceased",
    ["Art. I"],
  ],
  [
    "trust_type",
    "complex",
    "Complex: income distributions are discretionary; 160,000 of DNI retained and accumulated",
    ["Art. III(a)", "Art. IV(a)"],
  ],
  [
    "fai_definition",
    "illinois_pia_gains_to_principal",
    "Illinois Principal and Income Act as incorporated by Art. II; gains to principal (excluded from DNI)",
    ["Art. II"],
  ],
  [
    "trustee_fees",
    "principal",
    "Charged to principal (30,000 in 2025); still deductible in computing DNI",
    ["Art. V(c)"],
  ],
  ["principal_invaded", "no", "No. HEMS standard is ascertainable", ["Art. IV(b)"]],
  ["exemption", "complex_trust", "$100 (complex trust, §642(b))", []],
  ["election_65_day", "not_made", "Not made; window closed Mar 6, 2026", []],
];

const GOVERNED = new Set([
  "grantor_status",
  "trust_type",
  "fai_definition",
  "trustee_fees",
  "principal_invaded",
]);

function determinations(
  overrides: Partial<Record<InstrumentDeterminationOut["key"], [string, string]>> = {},
  locked = false,
): InstrumentDeterminationOut[] {
  return ROWS.map(([key, code, text, clauses]) => {
    const [c, t] = overrides[key] ?? [code, text];
    return {
      id: stableId(`instrument_determination:calloway:2025:${key}`),
      key,
      value_code: c,
      value_text: t,
      rationale_ref: null,
      citation_ids: clauses.map((l) => citationId(l, key)),
      clause_labels: clauses,
      set_by_kind: "agent",
      set_by_name: "Kevin Osei via Agent",
      suggestion_id: stableId(`suggestion:calloway:2025:${key}`),
      version: 1,
      clause_required: GOVERNED.has(key) && !locked,
    };
  });
}

const PROFILE: InstrumentOut["profile"] = {
  client_entity_id: INSTRUMENT_IDS.entity,
  fiduciary_kind: "trust",
  agreement_date: "2011-03-14",
  revocable: false,
  irrevocable_since: null,
  settlor_name: "Robert Calloway",
  settlor_died_year: 2019,
  residency_state: "IL",
  state_form: "IL-1041",
  ein: { kind: "ein", last4: "6614", presence: "on_file" },
};

const INSTRUMENT: NonNullable<InstrumentOut["instrument"]> = {
  id: INSTRUMENT_IDS.instrument,
  evidence_version_id: INSTRUMENT_IDS.version,
  file_name: AGREEMENT_FILE,
  page_count: AGREEMENT_PAGES,
  supersedes_instrument_id: null,
  attached_by_name: "Kevin Osei",
  attached_at: "2026-09-02T14:10:00-05:00",
};

const SEGMENTATION: NonNullable<InstrumentOut["segmentation"]> = {
  id: INSTRUMENT_IDS.segmentation,
  status: "segmented",
  text_source: "text_layer",
  confidence: "1.0000",
  clause_count: TREE.length,
};

const CITED_BY: InstrumentOut["cited_by"] = [
  {
    target: "trust_calculation",
    target_ref: "dni",
    label: "Trust Calculation · Distributable net income 400,000",
    clause_labels: ["Art. II", "Art. V(c)"],
  },
  {
    target: "trust_calculation",
    target_ref: "allocation",
    label: "Trust Calculation · Beneficiary allocation (Nora 160,000 · Theo 80,000)",
    clause_labels: ["Art. III(a)"],
  },
  {
    target: "return_field",
    target_ref: "f1041.type_of_entity",
    label: "Worksheets · 1041 page 1 · Type of entity: Complex trust ☒",
    clause_labels: ["Art. III(a)", "Art. IV(a)"],
  },
];

export const SCENARIO_NOTE = {
  banner: "Scenario: 25,000 of principal paid for Theo's tuition under Art. IV(b)",
  note: "Distributions of 265,000 carry out DNI under §661: Nora 160,000 · Theo 105,000 · trust retains 135,000",
} as const;

export type InstrumentState =
  "proposed" | "approved" | "invaded" | "unread" | "agents_off" | "reading" | "consent";

/** The TXT-01 read model of each state (a, b, c, d, d1, d2, d3; a2–a4 are interactions on a). */
export function callowayInstrument(state: InstrumentState): InstrumentOut {
  const approved = state === "approved";
  const read =
    state !== "unread" && state !== "agents_off" && state !== "reading" && state !== "consent";
  const reader: InstrumentOut["reader"] =
    state === "agents_off"
      ? {
          availability: "agents_off",
          consents_signed: 2,
          consents_required: 2,
          run_id: null,
          progress_label: null,
        }
      : state === "consent"
        ? {
            availability: "consent_required",
            consents_signed: 1,
            consents_required: 2,
            run_id: null,
            progress_label: null,
          }
        : state === "reading"
          ? {
              availability: "available",
              consents_signed: 2,
              consents_required: 2,
              run_id: INSTRUMENT_IDS.run,
              progress_label: "Checking citation 4 of 6",
            }
          : {
              availability: "available",
              consents_signed: 2,
              consents_required: 2,
              run_id: read ? INSTRUMENT_IDS.run : null,
              progress_label: null,
            };
  const invaded = state === "invaded";
  return {
    return_id: FIDUCIARY_IDS.callowayReturn,
    profile: PROFILE,
    instrument: INSTRUMENT,
    segmentation: SEGMENTATION,
    interpretation: read
      ? {
          id: INSTRUMENT_IDS.interpretation,
          status: approved ? "approved" : "adopted",
          scenario: invaded ? "principal_invaded" : "base",
          version_no: 1,
          content_hash: HASH,
          read_run_id: INSTRUMENT_IDS.run,
          adopted_by_name: "Kevin Osei",
          adopted_on: "2026-09-04",
          approved_by_name: approved ? "Samuel Ito" : null,
          approved_on: approved ? "2026-09-14" : null,
          clause_citation_count: 6,
          scenario_banner: invaded ? SCENARIO_NOTE.banner : null,
          scenario_note: invaded ? SCENARIO_NOTE.note : null,
        }
      : null,
    determinations: read
      ? determinations(
          invaded ? { principal_invaded: ["yes", "Yes — 25,000 (HEMS)"] } : {},
          approved,
        )
      : [],
    cited_by: read ? CITED_BY : [],
    reader,
    allowed_actions: approved
      ? ["instrument_interpretation.reopen", "sign_off.l3"]
      : [
          "instrument.attach",
          "instrument.read_run",
          "instrument_determination.edit",
          "sign_off.l3",
        ],
  };
}

export { CALLOWAY_TRUST };
