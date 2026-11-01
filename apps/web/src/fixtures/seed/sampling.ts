// A-03-T22 (TASK-2507; SPEC-580 AC-18): the AUD-11 and AUD-31 consumer fixtures, typed with the
// generated client so a breaking change to the sampling stub or C9 v2 fails `tsc`, and checked
// against the OpenAPI document by the contract tests. Values only from the handoff (AUD-11 a, f;
// AUD-31 f); what the design does not show stays null. Brightwater Hale, synthetic.
import type {
  ClientContactOut,
  CompletenessTieOut,
  DrawProgressOut,
  MappingRunOut,
  MappingSetSummaryOut,
  SampleItemOut,
  SampleSetOut,
  SampleSetSummaryOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

const ct = (iso: string): string => new Date(`${iso}-05:00`).toISOString();

/** AUD-11a card 3, in draw order: name, census ID, hire date. */
export const NORTHWIND_PARTICIPANTS: ReadonlyArray<readonly [string, string, string]> = [
  ["Alicia Brennan", "NW-1184", "2025-02-10"],
  ["Tomás Ibarra", "NW-0962", "2021-06-14"],
  ["Priyanka Desai", "NW-1203", "2025-04-07"],
  ["Gordon Whitfield", "NW-0418", "2012-09-04"],
  ["Mei Tanaka", "NW-1150", "2024-09-16"],
  ["Darnell Hughes", "NW-1022", "2023-03-06"],
  ["Sofia Marchetti", "NW-1219", "2025-06-02"],
  ["Kwame Mensah", "NW-1196", "2025-03-17"],
  ["Rebecca Lindgren", "NW-0877", "2019-10-21"],
  ["Hiroshi Nakamura", "NW-1171", "2024-11-04"],
  ["Ingrid Solberg", "NW-0731", "2017-02-13"],
  ["Felipe Navarro", "NW-1088", "2023-08-28"],
  ["Aisha Rahman", "NW-1230", "2025-07-14"],
  ["Connor Gallagher", "NW-0659", "2015-05-11"],
  ["Yuki Mori", "NW-1189", "2024-12-02"],
  ["Patrick Doyle", "NW-0990", "2022-01-10"],
  ["Leila Farahani", "NW-1142", "2024-07-08"],
  ["Andre Wilkins", "NW-1065", "2023-05-15"],
  ["Natalie Brooks", "NW-1211", "2025-05-05"],
  ["Vikram Sethi", "NW-0804", "2018-08-06"],
  ["Chloe Dubois", "NW-0712", "2016-11-14"],
  ["Benjamin Okoro", "NW-1158", "2024-10-07"],
  ["Teresa Romero", "NW-0935", "2020-12-07"],
  ["Ethan Caldwell", "NW-1004", "2022-06-27"],
  ["Fatima Qureshi", "NW-1224", "2025-02-03"],
];

export function participantItems(): SampleItemOut[] {
  return NORTHWIND_PARTICIPANTS.map(([name, key, hired], i) => ({
    position: i + 1,
    record_key: key,
    name,
    hire_date: hired,
    amount: null,
    selection_reason: "random",
    stratum_position: null,
  }));
}

const SHA = (label: string): string =>
  Array.from({ length: 64 }, (_, i) =>
    "0123456789abcdef".charAt((label.charCodeAt(i % label.length) + i) % 16),
  ).join("");

/** Northwind Robotics 401(k) PY2025, "Participants" Version 2, approved by Hannah Leclerc. */
export function northwindParticipants(): SampleSetOut {
  const engagement = stableId("engagement:northwind:2025");
  const workItem = stableId("work-item:northwind:2025");
  const census = stableId("population:northwind-census-v2");
  return {
    id: stableId("sample-set:northwind-participants"),
    engagement_id: engagement,
    work_item_id: workItem,
    title: "Participants",
    purpose: "Eligibility, contribution and pay-rate tests on the same 25 participants",
    program_step_key: null,
    version_no: 2,
    status: "approved",
    population: {
      id: census,
      engagement_id: engagement,
      work_item_id: workItem,
      source: {
        kind: "upload",
        evidence_version_id: stableId("evidence:northwind-census-v2"),
        file_name: "Northwind Census PY2025.xlsx",
        file_version_no: 2,
        uploaded_by_name: "Dana Kowalski",
        uploaded_on: "2026-09-16",
        gl_snapshot_id: null,
        connection_label: null,
        query: null,
        query_label: null,
        pulled_at: null,
      },
      record_count: 412,
      record_unit: "participants",
      amount_total: "14560000.00",
      sha256: SHA("northwind-census-v2"),
      sampling_unit: "participant (census record)",
      deviation_definition: "any attribute in EBP-03/EBP-04 not agreed to source",
      ties: [
        {
          id: stableId("tie:northwind:1"),
          position: 1,
          label: "PayGrid YTD register",
          left_amount: "14560000.00",
          comparisons: [
            {
              label: "PayGrid YTD register",
              amount: "14560000.00",
              citation: null,
              ledger_ref: null,
            },
          ],
          difference: "0.00",
          result: "tie",
          explanation: null,
          engine_version: "2.3",
          inputs_hash: SHA("tie:northwind:1"),
        },
        {
          id: stableId("tie:northwind:2"),
          position: 2,
          label: "W-3 Box 1 + Box 12 D",
          left_amount: "14560000.00",
          comparisons: [
            { label: "W-3 Box 1", amount: "13813400.00", citation: null, ledger_ref: null },
            { label: "W-3 Box 12 D", amount: "746600.00", citation: null, ledger_ref: null },
          ],
          difference: "0.00",
          result: "tie",
          explanation: null,
          engine_version: "2.3",
          inputs_hash: SHA("tie:northwind:2"),
        },
      ],
      created_by_name: "Marcus Delaney",
      created_at: ct("2026-09-16T15:12:00"),
    },
    parameters: {
      method: "attribute_nonstatistical",
      rmm: "moderate",
      tolerable_rate: "0.10",
      expected_rate: "0.00",
      confidence: "0.90",
      computed_size: 25,
      statistical_crosscheck_size: 22,
      override_size: null,
      override_rationale: null,
      final_size: 25,
      seed: 0x5e2a91,
      seed_hex: "0x5E2A91",
      seed_source: "scenario",
      sampler_version: "2.3",
      citations: [
        {
          label: "BH-EBP-210 step 3 · Table 2",
          citation_id: stableId("citation:bh-ebp-210-step-3-table-2"),
          verified: true,
        },
      ],
    },
    strata: [],
    items_total: 25,
    items_amount: null,
    versions: [
      {
        version_no: 2,
        status: "approved",
        population_id: census,
        population_label: "census v2",
        record_count: 412,
        tie_result: "tie",
        tie_difference: "0.00",
        seed_hex: "0x5E2A91",
        final_size: 25,
        override_pending: false,
        created_by_name: "Marcus Delaney",
        created_at: ct("2026-09-16T15:12:00"),
        prepared: {
          user_id: stableId("user:marcus-delaney"),
          name: "Marcus Delaney",
          initials: "MD",
          at: ct("2026-09-16T15:12:00"),
        },
        approved: {
          user_id: stableId("user:hannah-leclerc"),
          name: "Hannah Leclerc",
          initials: "HL",
          at: ct("2026-09-16T16:05:00"),
        },
      },
      {
        version_no: 1,
        status: "superseded",
        population_id: stableId("population:northwind-census-v1"),
        population_label: "census v1",
        record_count: 409,
        tie_result: "off",
        tie_difference: "-182300.00",
        seed_hex: "0x3C77D0",
        final_size: 25,
        override_pending: false,
        created_by_name: "Marcus Delaney",
        created_at: ct("2026-09-15T16:40:00"),
        prepared: null,
        approved: null,
      },
    ],
    inputs_hash: SHA("participants:v2:inputs"),
    items_hash: SHA("participants:v2:items"),
    content_hash: SHA("participants:v2:content"),
    allowed_actions: ["sample_set.export", "sample_set.generate_requests"],
  };
}

/** Granite Peak Outdoor Supply FY2026 (AUD-31 f): 128 accounts mapped and confirmed. */
export function granitePeakMapping(): MappingSetSummaryOut {
  return {
    id: stableId("mapping-set:granite-peak-fy2026"),
    engagement_id: stableId("engagement:granite-peak:fy2026"),
    trial_balance_id: stableId("trial-balance:granite-peak:fy2026"),
    trial_balance_version_no: 1,
    client_entity_id: stableId("entity:granite-peak-outdoor-supply"),
    entity_name: "Granite Peak Outdoor Supply",
    period_end: "2026-06-30",
    grouping_set_version_id: stableId("grouping-set-version:bh-fs-groupings:1"),
    grouping_set_label: "BH FS groupings v1",
    prior_source: "prior_engagement",
    run_status: "ready",
    status: "prepared",
    tallies: {
      accounts: 128,
      mapped: 128,
      need_review: 0,
      prior_year_match: null,
      number_range: null,
      edited: null,
      tb_balanced: 1,
      tb_count: 1,
    },
    sign_offs: [
      {
        level: 1,
        initials: "CD",
        name: "Caleb Dunn",
        at: ct("2026-09-14T11:40:00"),
        stale: false,
      },
    ],
    content_hash: SHA("granite-peak-fy2026-mapping-v1"),
  };
}

export function granitePeakRun(): MappingRunOut {
  return {
    mapping_set_id: stableId("mapping-set:granite-peak-fy2026"),
    run_status: "ready",
    run_done: 128,
    run_total: 128,
    failure_code: null,
  };
}

/** AUD-11 b (A-03-T11): Version 2 "Prepared · MD", not yet approved, so Generate is disabled. */
export function northwindParticipantsDraft(): SampleSetOut {
  const approved = northwindParticipants();
  const [v2, v1] = approved.versions;
  if (v2 === undefined || v1 === undefined) throw new Error("the seed has two versions");
  return {
    ...approved,
    status: "draft",
    versions: [{ ...v2, status: "draft", approved: null }, v1],
    allowed_actions: ["sample_set.export", "sample_set.create", "sign_off.prepare"],
  };
}

/** AUD-11's picker (DF-05; DV-A4): Northwind's two sample sets on the work item. */
export function northwindSampleSets(): SampleSetSummaryOut[] {
  return [
    {
      id: stableId("sample-set:northwind-participants"),
      title: "Participants",
      current_version_no: 2,
      status: "approved",
      final_size: 25,
      population_count: 412,
    },
    {
      id: stableId("sample-set:northwind-distributions"),
      title: "Distributions",
      current_version_no: 1,
      status: "draft",
      final_size: 10,
      population_count: 64,
    },
  ];
}

// --- A-03-T15: AUD-11 c, e and f -----------------------------------------------------------------

/** AUD-11 c: who the five requests per participant go to (the GENERATE SHEET's recipients). */
export const DANA = stableId("contact:northwind:dana-kowalski");
export const SAM = stableId("contact:keystone:sam-ortiz");

export function generateContacts(): ClientContactOut[] {
  return [
    {
      kind: "member",
      id: DANA,
      role: "client_admin",
      email: "dana.kowalski@northwindrobotics.example",
      expires_at: null,
      display_name: "Dana Kowalski",
    },
    {
      kind: "member",
      id: SAM,
      role: "third_party",
      email: "sam.ortiz@keystone-rs.example",
      expires_at: null,
      display_name: "Sam Ortiz",
    },
  ];
}

/** AUD-11 c: the sheet's five templates per participant, verbatim from the handoff. */
export const GENERATE_TEMPLATES: ReadonlyArray<{
  description: string;
  contactId: string;
  thirdParty: boolean;
}> = [
  { description: "New-hire record (PayGrid)", contactId: DANA, thirdParty: false },
  { description: "Deferral election or opt-out form", contactId: DANA, thirdParty: false },
  { description: "Paystub, Dec 12, 2025 payroll", contactId: DANA, thirdParty: false },
  { description: "Pay rate authorization", contactId: DANA, thirdParty: false },
  { description: "Q4 2025 participant statement", contactId: SAM, thirdParty: true },
];
export const GENERATE_DUE = "2026-10-01";

/** AUD-11 e: Version 3 drawing — a person's draw, the first eight participants in. */
export function northwindParticipantsDrawing(): SampleSetOut {
  const approved = northwindParticipants();
  const [v2, v1] = approved.versions;
  if (v2 === undefined || v1 === undefined) throw new Error("the seed has two versions");
  return {
    ...approved,
    version_no: 3,
    status: "drawing",
    items_hash: null,
    content_hash: null,
    versions: [
      {
        ...v2,
        version_no: 3,
        status: "drawing",
        prepared: null,
        approved: null,
        created_at: ct("2026-09-24T09:24:00"),
      },
      v2,
      v1,
    ],
    allowed_actions: [],
  };
}

export function drawProgress(done: number): DrawProgressOut {
  return {
    version_no: 3,
    status: "drawing",
    items_done: done,
    items_total: 25,
    failure_code: null,
    items: participantItems().slice(0, done),
  };
}

/** AUD-11 f (R2): Granite Peak FY2026 · BH-FS-430, a general-ledger population and its strata. */
export function graniteDisbursements(): SampleSetOut {
  const engagement = stableId("engagement:granite-peak:fy2026");
  const workItem = stableId("work-item:granite-peak:fy2026");
  const population = stableId("population:granite-peak-disbursements");
  const tie = (n: number, label: string, amount: string | null): CompletenessTieOut => ({
    id: stableId(`tie:granite-peak:${String(n)}`),
    position: n,
    label,
    left_amount: amount,
    comparisons: amount === null ? [] : [{ label, amount, citation: null, ledger_ref: null }],
    difference: amount === null ? null : "0.00",
    result: "tie",
    explanation: null,
    engine_version: "2.3",
    inputs_hash: SHA(`tie:granite-peak:${String(n)}`),
  });
  return {
    id: stableId("sample-set:granite-peak-disbursements"),
    engagement_id: engagement,
    work_item_id: workItem,
    title: "Disbursements",
    purpose: null,
    program_step_key: null,
    version_no: 1,
    status: "draft",
    population: {
      id: population,
      engagement_id: engagement,
      work_item_id: workItem,
      source: {
        kind: "general_ledger",
        evidence_version_id: null,
        file_name: null,
        file_version_no: null,
        uploaded_by_name: null,
        uploaded_on: null,
        gl_snapshot_id: stableId("gl-snapshot:granite-peak-fy2026"),
        connection_label: "NetSuite · Granite Peak Outdoor Supply",
        query: null,
        query_label: "Disbursements Jul 1 – Sep 18, 2026",
        pulled_at: ct("2026-09-24T10:18:00"),
      },
      record_count: 1912,
      record_unit: "payments",
      amount_total: "38640200.00",
      sha256: SHA("granite-peak-disbursements-fy2026"),
      sampling_unit: "payment",
      deviation_definition: null,
      ties: [
        tie(1, "Front Range Bank operating account cash disbursements", "38640200.00"),
        tie(2, "No gaps in check numbers · ACH batch totals agree", null),
      ],
      created_by_name: "Simone Baptiste",
      created_at: ct("2026-09-24T10:18:00"),
    },
    parameters: {
      method: "threshold_random_stratified",
      rmm: null,
      tolerable_rate: null,
      expected_rate: null,
      confidence: null,
      computed_size: 40,
      statistical_crosscheck_size: null,
      override_size: null,
      override_rationale: null,
      final_size: 40,
      seed: 0x7c31b4,
      seed_hex: "0x7C31B4",
      seed_source: "scenario",
      sampler_version: "2.3",
      citations: [],
    },
    strata: [
      {
        position: 1,
        min_amount: "50000.00",
        max_amount: null,
        test_rule: "all",
        random_count: null,
        population_count: 24,
        population_amount: null,
        selected_count: 24,
      },
      {
        position: 2,
        min_amount: "7750.00",
        max_amount: "49999.99",
        test_rule: "random",
        random_count: 16,
        population_count: 1102,
        population_amount: null,
        selected_count: 16,
      },
      {
        position: 3,
        min_amount: null,
        max_amount: "7750.00",
        test_rule: "none",
        random_count: null,
        population_count: 786,
        population_amount: null,
        selected_count: 0,
      },
    ],
    items_total: 40,
    items_amount: "3698700.00",
    versions: [
      {
        version_no: 1,
        status: "draft",
        population_id: population,
        population_label: "Disbursements Jul 1 – Sep 18, 2026",
        record_count: 1912,
        tie_result: "tie",
        tie_difference: "0.00",
        seed_hex: "0x7C31B4",
        final_size: 40,
        override_pending: false,
        created_by_name: "Simone Baptiste",
        created_at: ct("2026-09-24T10:20:00"),
        prepared: null,
        approved: null,
      },
    ],
    inputs_hash: SHA("disbursements:v1:inputs"),
    items_hash: SHA("disbursements:v1:items"),
    content_hash: SHA("disbursements:v1:content"),
    allowed_actions: ["sample_set.export", "sample_set.create"],
  };
}

export function graniteSampleSets(): SampleSetSummaryOut[] {
  return [
    {
      id: stableId("sample-set:granite-peak-disbursements"),
      title: "Disbursements",
      current_version_no: 1,
      status: "draft",
      final_size: 40,
      population_count: 1912,
    },
  ];
}
