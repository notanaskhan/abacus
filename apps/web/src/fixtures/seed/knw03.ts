// KNW-03 Program editor (K-01-T13; K-01 §3.4 AC4.1–4.3; KNW-03 handoff spec and R2): BH Audit
// Methodology · EBP v3 published, its seven programs as KNW-03's rail reads them (16·8 · 8·3 ·
// 6·2 · 8·2 · 10·3 · 7·1 · 12·2 = 67 · 21), BH-EBP-110's sixteen steps verbatim from the steps
// table, step 9's Risk Assessment guidance, the PBC template rows the steps link to, and the one
// AUD-04 citation of step 4. v2's BH-EBP-110 is the same program less step 15 with steps 7, 9 and
// 10 as KNW-02 c says they changed; the handoff draws no v2 wording, so those three rows are
// fixture stand-ins (DEC-1269) until the importer's v2 export replaces them.
import type {
  AbacusModulesMethodologyContractStepOut as StepOut,
  AgentRunOut,
  GuidanceBlockOut,
  TemplateItemOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export const KNW03_CLOCK = "2026-09-14T14:30:00-05:00";

export const KNW03_PROGRAMS: readonly (readonly [
  code: string,
  name: string,
  steps: number,
  mandatory: number,
])[] = [
  ["BH-EBP-110", "General Planning", 16, 8],
  ["BH-EBP-140", "Service Organizations", 8, 3],
  ["BH-EBP-210", "Sampling", 6, 2],
  ["BH-EBP-310", "Investments & Certification", 8, 2],
  ["BH-EBP-410", "Contributions", 10, 3],
  ["BH-EBP-510", "Form 5500 & Supplemental Schedules", 7, 1],
  ["BH-EBP-610", "Completion & Reporting", 12, 2],
];

/** The PBC template's rows the steps link to, in template order (`pbc_positions` are 1-based). */
export const KNW03_PBC: readonly string[] = [
  "Engagement letter",
  "Plan document & amendments",
  "Trust agreement",
  "IRS opinion letter",
  "SOC 1 reports",
  "Amendments",
  "Net trust assets",
  "Account balances",
  "Fraud inquiries",
  "Parties-in-interest list",
  "Plan-level adjustments",
  "Remittance report",
];

export const KNW03_ITEMS: TemplateItemOut[] = KNW03_PBC.map((description) => ({
  area_code: "planning",
  description,
  tier: "core",
}));

type Level = StepOut["level"];

interface Row {
  text: string;
  assertions: string[];
  standard: string;
  pbc: number[];
  level: Level;
  mandatory: boolean;
  lockNote?: string;
}

/** The steps table, verbatim (KNW-03 spec, LAYOUT · CANVAS). */
const ROWS_110: readonly Row[] = [
  {
    text: "Acceptance or continuance and signed letter incl. §103(a)(3)(C) election",
    assertions: [],
    standard: "AU-C 210, 703",
    pbc: [1],
    level: "foundation",
    mandatory: true,
  },
  {
    text: "Team independence confirmations",
    assertions: [],
    standard: "AU-C 220",
    pbc: [],
    level: "foundation",
    mandatory: true,
  },
  {
    text: "Plan documents, amendments, SPD, trust agreement, IRS letter",
    assertions: [],
    standard: "AU-C 315",
    pbc: [2, 3, 4],
    level: "foundation",
    mandatory: false,
  },
  {
    text: "Service organizations relevant to the plan → BH-EBP-140",
    assertions: [],
    standard: "AU-C 402",
    pbc: [5],
    level: "planning",
    mandatory: false,
  },
  {
    text: "Plan changes and prior-year matters",
    assertions: [],
    standard: "AU-C 315",
    pbc: [6],
    level: "planning",
    mandatory: false,
  },
  {
    text: "Plan trial balance from trustee and recordkeeper reports",
    assertions: ["All"],
    standard: "AU-C 500",
    pbc: [7, 8],
    level: "foundation",
    mandatory: false,
  },
  {
    text: "Materiality on net assets (1.0%–2.0%); PM 50%–75%; CT 5%",
    assertions: [],
    standard: "AU-C 320, 450",
    pbc: [],
    level: "planning",
    mandatory: true,
    lockNote: "Reserved to EP",
  },
  {
    text: "Understand the plan and its internal control, including IT",
    assertions: [],
    standard: "AU-C 315",
    pbc: [],
    level: "planning",
    mandatory: false,
  },
  {
    text: "Fraud: team discussion led by the EP; inquiries; presumed risks",
    assertions: [],
    standard: "AU-C 240",
    pbc: [9],
    level: "planning",
    mandatory: true,
  },
  {
    text: "Assess risks at the FS and assertion levels; significant risks to EP",
    assertions: ["All"],
    standard: "AU-C 315, 330",
    pbc: [],
    level: "planning",
    mandatory: true,
  },
  {
    text: "Related parties and parties in interest",
    assertions: ["Completeness"],
    standard: "AU-C 550",
    pbc: [10],
    level: "planning",
    mandatory: false,
  },
  {
    text: "Journal entries and other adjustments (management override)",
    assertions: ["All"],
    standard: "AU-C 240",
    pbc: [11],
    level: "testing",
    mandatory: true,
  },
  {
    text: "Planning analytical procedures",
    assertions: [],
    standard: "AU-C 520",
    pbc: [],
    level: "planning",
    mandatory: false,
  },
  {
    text: "Parties in interest and Schedule H line 4a (incl. late deposits)",
    assertions: ["Presentation"],
    standard: "AU-C 703",
    pbc: [12],
    level: "testing",
    mandatory: false,
  },
  {
    text: "Technology resources: agent runs used and who adopted the output",
    assertions: [],
    standard: "SQMS 1",
    pbc: [],
    level: "completion",
    mandatory: true,
  },
  {
    text: "AU-C 260 planning communication to the benefits committee",
    assertions: [],
    standard: "AU-C 260",
    pbc: [],
    level: "planning",
    mandatory: true,
  },
];

/** Step 9's guidance: the Risk Assessment block (KNW-03 spec, DOCK). */
const RISK_ASSESSMENT: GuidanceBlockOut[] = [
  {
    kind: "paragraph",
    text: "The firm documents the overall risks to the financial statements, including fraud risks: weaknesses in the control environment, or incentives for management to misstate. Presumed fraud risks:",
    items: [],
    strong: [],
  },
  {
    kind: "ordered_list",
    text: null,
    items: [
      "Management override of controls — prepopulated as a mandatory significant fraud risk at the financial statement level under AU-C 240. The firm's standard response adds procedures to the general audit programs, including experienced staffing and journal entry testing.",
      "Improper revenue recognition — for employee benefit plans this concerns the plan's principal inflows: employer and employee contributions.",
    ],
    strong: [],
  },
];

export const KNW03_GUIDANCE_TITLE = "Risk Assessment";
export const KNW03_PREPOPULATES =
  "Prepopulated from step 9 into Risk Assessment on 14 engagements · mandatory · cannot be rebutted (item 1)";

function stepsOf(version: "v2" | "v3"): StepOut[] {
  const rows = ROWS_110.map((r, i) => ({ r, n: i + 1 })).filter(
    ({ n }) => version === "v3" || n !== 15,
  );
  return rows.map(({ r, n }) => {
    // v2 stand-ins for the three steps KNW-02 c lists as changed (DEC-1269).
    const v2 = version === "v2";
    const text =
      v2 && n === 7
        ? "Materiality: net assets available for benefits, 1.0%–2.0%; PM 50%–75%; clearly trivial 5%"
        : v2 && n === 9
          ? "Fraud: team discussion; inquiries; presumed risks"
          : r.text;
    return {
      id: stableId(`methodology:step:110:${version}:${String(n)}`),
      step_key: `ebp-110-${String(n)}`,
      anchor: `ebp-110-${String(n)}@${version}`,
      number: n,
      text,
      assertions: r.assertions,
      standard_refs: [r.standard],
      level: r.level,
      mandatory: v2 && n === 10 ? false : r.mandatory,
      lock_note: r.lockNote ?? null,
      guidance: n === 9 && !v2 ? RISK_ASSESSMENT : [],
      prepopulates: n === 9 && !v2 ? ["risk_assessment"] : [],
      depends_on_step_keys: [],
      pbc_positions: r.pbc,
      origin: "workbook",
      parse_flag: null,
      flag_resolution: null,
      rules_count: 0,
      row_version: 1,
      allowed_actions: [],
    };
  });
}

export const KNW03_STEPS_V3 = stepsOf("v3");
export const KNW03_STEPS_V2 = stepsOf("v2");

/** The AUD-04 citation of step 4 (SHL-07 popover, b): the step's full wording as cited. */
export const KNW03_STEP4_QUOTE =
  "4. Determine whether the plan uses service organizations whose services are relevant to the plan's financial statements and whose controls are significant to the plan's internal control. If any are, perform the procedures in BH-EBP-140 Service Organizations.";
export const KNW03_POPOVER_TITLE = "BH-EBP-110: General Planning Procedures";
export const KNW03_CITED_IN = {
  host: "Northwind Robotics 401(k) Plan",
  where: "General Audit Planning › Service Organizations",
};

// --- K-01-T15: KNW-03 c (a draft), d (tailored on an engagement) and f (Fix in Knowledge) -------

/** BH-EBP-140 Service Organizations at v3, as KNW-03 f draws it (8 steps, 3 locked); step 8 is new
 * in v3, published as guidance, not mandatory. Texts are the artboard's, completed past its
 * two-line clamp (DEC-1455). */
const ROWS_140: readonly Row[] = [
  {
    text: "Identify service organizations",
    assertions: [],
    standard: "AU-C 402",
    pbc: [],
    level: "foundation",
    mandatory: true,
  },
  {
    text: "Obtain SOC 1 Type 2 reports",
    assertions: [],
    standard: "AU-C 402",
    pbc: [5],
    level: "foundation",
    mandatory: true,
  },
  {
    text: "Carved-out subservice organizations",
    assertions: [],
    standard: "AU-C 402",
    pbc: [5],
    level: "planning",
    mandatory: false,
  },
  {
    text: "Evaluate the service auditor's report",
    assertions: [],
    standard: "AU-C 402",
    pbc: [],
    level: "planning",
    mandatory: true,
  },
  {
    text: "Test the plan's complementary user entity controls",
    assertions: ["All"],
    standard: "AU-C 402",
    pbc: [],
    level: "testing",
    mandatory: false,
  },
  {
    text: "Recordkeeper and trustee reconciliations",
    assertions: ["Existence"],
    standard: "AU-C 500",
    pbc: [],
    level: "testing",
    mandatory: false,
  },
  {
    text: "Payroll provider controls over contributions",
    assertions: ["Accuracy"],
    standard: "AU-C 402",
    pbc: [],
    level: "testing",
    mandatory: false,
  },
  {
    text: "Bridge letter and gap-period procedures when the SOC 1 period does not reach plan year-end",
    assertions: [],
    standard: "AU-C 402",
    pbc: [],
    level: "testing",
    mandatory: false,
  },
];

const SERVICE_ORGANIZATIONS: GuidanceBlockOut[] = [
  {
    kind: "paragraph",
    text: "Service organizations whose controls are significant to the plan need a SOC 1 Type 2 report that covers the plan year. When the report period ends before plan year-end, the gap needs a bridge letter and gap-period procedures.",
    items: [],
    strong: [],
  },
];
export const KNW03_SERVICE_ORGS_TITLE = "Service organizations";
export const KNW03_STEP8_NOTE =
  "Step 8 is published as guidance, not mandatory. The pack points to a bridge-letter template that v3 does not include.";

export const KNW03_STEPS_140: StepOut[] = ROWS_140.map((r, i) => {
  const n = i + 1;
  return {
    id: stableId(`methodology:step:140:v3:${String(n)}`),
    step_key: `ebp-140-${String(n)}`,
    anchor: `ebp-140-${String(n)}@v3`,
    number: n,
    text: r.text,
    assertions: r.assertions,
    standard_refs: [r.standard],
    level: r.level,
    mandatory: r.mandatory,
    lock_note: null,
    guidance: n === 8 ? SERVICE_ORGANIZATIONS : [],
    prepopulates: [],
    depends_on_step_keys: [],
    pbc_positions: r.pbc,
    origin: "workbook",
    parse_flag: null,
    flag_resolution: null,
    rules_count: 0,
    row_version: 1,
    allowed_actions: [],
  };
});

/** f: the Northwind Internal Control run that failed at 9:58 AM on BH-EBP-140 step 8 (C6 v1). */
export const KNW03_RUN_ID = stableId("agent-run:northwind-internal-control-0958");
export const KNW03_RUN_ERROR =
  "Pack configuration error: BH-EBP-140 step 8 points to a SOC 1 bridge-letter template that EBP v3 does not include. No evidence written.";
export const KNW03_RUN: AgentRunOut = {
  id: KNW03_RUN_ID,
  agent: "internal_control",
  agent_label: "Internal Control",
  subject: "Northwind Robotics 401(k) Plan · BH-EBP-140 step 8",
  state: "failed",
  state_reason: KNW03_RUN_ERROR,
  started_at: "2026-09-14T14:58:00Z",
  finished_at: "2026-09-14T14:58:20Z",
  duration_ms: 20000,
  initiator_name: "Hannah Leclerc",
};

/** c: Hannah Leclerc's draft v4 of BH-EBP-110, drafted from v3. Optional steps are hers to edit
 * and remove; mandatory steps stay locked to the QM owner (no action on them). */
export const KNW03_STEPS_V4: StepOut[] = KNW03_STEPS_V3.map((s) => ({
  ...s,
  id: stableId(`methodology:step:110:v4:${String(s.number)}`),
  anchor: `${s.step_key}@v4`,
  allowed_actions: s.mandatory ? [] : ["methodology.edit_step", "methodology.remove_step"],
}));

/** d: A-04's tailoring of BH-EBP-110 on the Northwind engagement (fixture-only until A-04's read). */
export const KNW03_TAILORING = {
  engagement: "Northwind Robotics 401(k) Plan",
  steps: {
    "ebp-110-11": {
      kind: "tailored",
      text: "Tailored — rationale: no related-party transactions outside Northwind Robotics, Inc.",
    },
    "ebp-110-7": { kind: "decided", text: "Decided 1.5% · Margaret Okonkwo" },
  },
} as const;
