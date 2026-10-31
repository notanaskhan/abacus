// KNW-02's workbook slice in fixture mode (K-01-T07; K-01 §3.3, §4): BH Audit Methodology · EBP v3
// imported from the workbook, in Needs review, its seven programs and BH-EBP-110's parsed steps,
// the approval checklist the server computes, approve (supersedes v2) and the workbook upload with
// its row problems. Program reads are K-01-T12's (stubbed on main); here they answer from the
// handoff's figures: 16 + 8 + 6 + 8 + 10 + 7 + 12 = 67 steps.

import type {
  AbacusModulesMethodologyContractStepOut as StepOut,
  ApproveVersionIn,
  DiffRowOut,
  ListPageVersionActivityOut,
  StandardsMappingIn,
  VersionActivityOut,
  VersionDiffOut,
  MethodologyVersionOut,
  ProgramOut,
  TemplateVersionOut,
  VersionStateOut,
} from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { stableId } from "../seed/prng";

export const TEMPLATE = "BH Audit Methodology · EBP";
export const TEMPLATE_ID = stableId("methodology:template:ebp");
export const V3 = stableId("methodology:version:ebp-v3");
export const V2 = stableId("methodology:version:ebp-v2");
/** K-01-T19: Hannah Leclerc's draft v4 from v3 (KNW-03 c), opened for review in KNW-02. */
export const V4 = stableId("methodology:version:ebp-v4");
export const HANNAH = { user_id: stableId("user:hannah-leclerc"), name: "Hannah Leclerc" };
export const MARGARET = { user_id: stableId("user:margaret-okonkwo"), name: "Margaret Okonkwo" };
const CREATED = "2026-01-12T19:52:00Z";
const HASH = `sha256:${"a3".repeat(32)}`;

const PROGRAMS: readonly (readonly [string, string, number, number])[] = [
  ["BH-EBP-110", "General Planning", 16, 8],
  ["BH-EBP-140", "Service Organizations", 8, 2],
  ["BH-EBP-210", "Sampling", 6, 2],
  ["BH-EBP-310", "Investments & Certification", 8, 3],
  ["BH-EBP-410", "Contributions", 10, 2],
  ["BH-EBP-510", "Form 5500 & Supplemental Schedules", 7, 1],
  ["BH-EBP-610", "Completion & Reporting", 12, 3],
];
export const programId = (code: string): string => stableId(`methodology:program:${code}`);

/** BH-EBP-110's first eight steps, as the handoff's sheet lists them (the workbook's text). */
const STEPS_110: readonly (readonly [string, boolean])[] = [
  [
    "Confirm acceptance or continuance and the signed engagement letter, including the §103(a)(3)(C) election",
    true,
  ],
  ["Obtain independence confirmations from every team member", true],
  ["Obtain plan documents, amendments, SPD, trust agreement and IRS letter", false],
  ["Service organizations relevant to the plan → BH-EBP-140", false],
  ["Plan changes and prior-year matters", false],
  ["Build the plan trial balance from the trustee and recordkeeper reports", false],
  [
    "Materiality: net assets available for benefits, 1.0%–2.0%; PM 50%–75%; clearly trivial 5%",
    true,
  ],
  ["Understand the plan and its internal control, including IT", false],
];

// ---- K-01-T19: KNW-02 c (diff), d (standards mapping) and the Activity tab ---------------------

const row = (
  kind: DiffRowOut["kind"],
  code: number,
  number: number,
  before: string | null,
  after: string | null,
): DiffRowOut => ({
  kind,
  program_code: `BH-EBP-${String(code)}`,
  number,
  step_key: `ebp-${String(code)}-${String(number)}`,
  before_text: before,
  after_text: after,
  changed_fields: kind === "changed" ? ["text"] : [],
});

/** KNW-02 c, verbatim where the artboard draws a row; the two changed rows and the removed row
 * below its fold read as the loader's structural text (K-01-T18's seed, DEC-1756). */
export const DIFF_V3_V2: readonly DiffRowOut[] = [
  row(
    "added",
    110,
    15,
    null,
    "Document technology resources used (agent runs) and who adopted their output",
  ),
  row(
    "added",
    140,
    8,
    null,
    "Bridge letter and gap-period procedures when the SOC 1 period does not reach plan year-end",
  ),
  row("added", 410, 7, null, "Late deposits: lost earnings (DOL VFCP calculator) and Form 5330"),
  row(
    "added",
    510,
    6,
    null,
    "Tie the draft Form 5500 Schedule H to the financial statements line by line",
  ),
  row(
    "changed",
    110,
    7,
    "Materiality: total plan assets, 1.0%–2.0%; PM 60%–75%",
    "Materiality: net assets available for benefits, 1.0%–2.0%; PM 50%–75%; clearly trivial 5%",
  ),
  row(
    "changed",
    110,
    9,
    "Hold the fraud discussion with the engagement team",
    "Fraud discussion led by the engagement partner; minutes approved by the EP",
  ),
  row(
    "changed",
    110,
    10,
    "Assess inherent risk as low, moderate or high",
    "Assess inherent risk on a spectrum for each relevant assertion (SAS 145)",
  ),
  row(
    "changed",
    140,
    3,
    "Identify subservice organizations",
    "Carved-out subservice organizations: obtain and evaluate CUECs and the subservice controls",
  ),
  row(
    "changed",
    210,
    2,
    "Document the sample selection method",
    "Record the sampling seed and the population used",
  ),
  row(
    "changed",
    310,
    1,
    "Read the limited-scope certification",
    "§103(a)(3)(C) certification: wording, certifying institution and scope",
  ),
  row(
    "changed",
    410,
    6,
    "Test contribution cutoff",
    "Cutoff of the last payroll of the year: deferrals withheld and deposited after year-end",
  ),
  row("changed", 510, 2, "BH-EBP-510 step 2", "BH-EBP-510 step 2 (revised in v3)"),
  row("changed", 610, 8, "BH-EBP-610 step 8", "BH-EBP-610 step 8 (revised in v3)"),
  row("removed", 310, 9, "BH-EBP-310 step 9", null),
];

/** Hannah's v4 against v3 (KNW-03 c): step 17 added, step 11 edited. */
export const DIFF_V4_V3: readonly DiffRowOut[] = [
  row("changed", 110, 11, "BH-EBP-110 step 11", "BH-EBP-110 step 11 (tailored wording)"),
  row("added", 110, 17, null, "BH-EBP-110 step 17"),
];

function diffOut(
  version: string,
  against: string,
  rows: readonly DiffRowOut[],
  unchanged: number,
): VersionDiffOut {
  const count = (k: DiffRowOut["kind"]): number => rows.filter((r) => r.kind === k).length;
  return {
    version_id: version,
    against_version_id: against,
    against_label: against === V2 ? "v2" : "v3",
    tiles: {
      added: count("added"),
      changed: count("changed"),
      removed: count("removed"),
      unchanged,
    },
    rows: [...rows],
  };
}

/** KNW-02 d: the EBP types the mapping names (codes; the screen words them). */
export const EBP_TYPES = ["ebp_dc_limited_scope", "ebp_dc_full_scope", "ebp_db"] as const;
const STANDARDS_SET = stableId("standards-set:gaas-nonissuer-au-c-703");

function activity(version: string): VersionActivityOut[] {
  const ev = (
    seq: number,
    kind: string,
    who: { user_id: string; name: string },
    at: string,
  ): VersionActivityOut => ({
    seq,
    kind,
    actor_kind: "human",
    actor_user_id: who.user_id,
    actor_name: who.name,
    at,
    facts: {},
  });
  return version === V4
    ? [
        ev(1, "draft_created", HANNAH, "2026-10-01T15:02:00Z"),
        ev(2, "step_edited", HANNAH, "2026-10-01T15:06:00Z"),
        ev(3, "step_added", HANNAH, "2026-10-01T15:09:00Z"),
      ]
    : [
        ev(1, "imported", MARGARET, "2026-01-12T19:52:00Z"),
        ev(2, "standards_mapped", MARGARET, "2026-01-12T20:12:00Z"),
      ];
}

export interface MethodologySetup {
  status: "needs_review" | "published";
  /** Instants the approval stamps (f: 2:31 PM). */
  approvedAt: string;
  /** What the persona may do (Margaret: approve; Hannah: manage only). */
  actions?: readonly string[];
  /** K-01-T19: Hannah's draft v4 exists (draft review). */
  withDraft?: boolean;
}

export function methodologyHandlers(setup: MethodologySetup): Record<string, FixtureHandler> {
  let status: VersionStateOut["status"] = setup.status;
  let approvedAt: string | null = setup.status === "published" ? setup.approvedAt : null;
  let effectiveFrom: string | null = setup.status === "published" ? "2026-01-01" : null;
  let rowVersion = setup.status === "published" ? 2 : 1;
  const actions = setup.actions ?? ["approve", "manage"];
  // KNW-02 d's mapping on v3 (the draft v4 keeps v3's).
  let mapping: Omit<StandardsMappingIn, "row_version"> = {
    standards_set_id: STANDARDS_SET,
    quality_management_ref: "SQMS 1 (effective Dec 15, 2025)",
    engagement_types: [...EBP_TYPES],
    default_for_new_engagements: true,
  };

  const state = (id: string): VersionStateOut =>
    id === V2
      ? {
          version_id: V2,
          template_id: TEMPLATE_ID,
          label: "v2",
          status: status === "published" ? "superseded" : "published",
          approval_basis: "approved",
          approved_at: "2025-01-14T16:05:00Z",
          approved_by_name: MARGARET.name,
          approved_by_user_id: MARGARET.user_id,
          effective_from: "2025-01-01",
          effective_to: status === "published" ? "2025-12-31" : null,
          default_for_new_engagements: status !== "published",
          drafted_from_version_id: null,
          engagement_types: ["ebp_audit"],
          standards_set_id: null,
          row_version: 3,
          allowed_actions: [],
        }
      : {
          version_id: V3,
          template_id: TEMPLATE_ID,
          label: "v3",
          status,
          approval_basis: status === "published" ? "approved" : null,
          approved_at: approvedAt,
          approved_by_name: approvedAt === null ? null : MARGARET.name,
          approved_by_user_id: approvedAt === null ? null : MARGARET.user_id,
          effective_from: effectiveFrom,
          effective_to: null,
          default_for_new_engagements: mapping.default_for_new_engagements,
          drafted_from_version_id: null,
          engagement_types: [...mapping.engagement_types],
          standards_set_id: mapping.standards_set_id,
          standards_set_code: mapping.standards_set_id === null ? null : "gaas_nonissuer_au_c_703",
          standards_set_label:
            mapping.standards_set_id === null
              ? null
              : "GAAS nonissuer · AU-C 703 · plan years ending on or after Dec 31, 2025",
          quality_management_ref: mapping.quality_management_ref ?? null,
          row_version: rowVersion,
          checklist: [
            { code: "has_programs", ok: true, n: PROGRAMS.length },
            { code: "has_steps", ok: true, n: 67 },
            { code: "every_program_has_steps", ok: true, n: 0 },
          ],
          checklist_hash: HASH,
          allowed_actions: status === "needs_review" ? [...actions] : [],
        };

  const draft = (): VersionStateOut => ({
    ...state(V3),
    version_id: V4,
    label: "v4",
    status: "draft",
    approval_basis: null,
    approved_at: null,
    approved_by_name: null,
    approved_by_user_id: null,
    effective_from: null,
    default_for_new_engagements: false,
    drafted_from_version_id: V3,
    row_version: 3,
    allowed_actions: actions.includes("manage") ? ["manage"] : [],
  });

  const summary = (id: string): TemplateVersionOut => ({
    template_id: TEMPLATE_ID,
    template_name: TEMPLATE,
    version: id === V2 ? 2 : id === V4 ? 4 : 3,
    version_id: id,
    created_at: CREATED,
    engagement_types: ["ebp_audit"],
  });

  const programs = (): ProgramOut[] =>
    PROGRAMS.map(([code, name, steps, mandatory], n) => ({
      id: programId(code),
      version: state(V3),
      code,
      name,
      position: n + 1,
      step_count: steps,
      mandatory_count: mandatory,
      flags_open: 0,
      counts_by_level: {},
    }));

  const steps = (program: string): StepOut[] =>
    program !== programId("BH-EBP-110")
      ? []
      : STEPS_110.map(([text, mandatory], n) => ({
          id: stableId(`methodology:step:110:${String(n + 1)}`),
          step_key: `ebp-110-${String(n + 1)}`,
          anchor: `ebp-110-${String(n + 1)}@v3`,
          number: n + 1,
          text,
          assertions: [],
          standard_refs: [],
          level: n < 2 ? "foundation" : "planning",
          mandatory,
          lock_note: null,
          guidance: [],
          prepopulates: [],
          depends_on_step_keys: [],
          pbc_positions: [],
          origin: "workbook",
          parse_flag: null,
          flag_resolution: null,
          rules_count: 0,
          row_version: 1,
          allowed_actions: [],
        }));

  return {
    "GET /v1/methodology/templates": () =>
      json([...(setup.withDraft === true ? [summary(V4)] : []), summary(V3), summary(V2)]),
    "GET /v1/methodology/versions/{version_id}": ({ params }) =>
      json({
        summary: summary(params.version_id ?? V3),
        areas: [],
        items: [],
        rules: [],
      } satisfies MethodologyVersionOut),
    "GET /v1/methodology/versions/{version_id}/state": ({ params }) =>
      json(params.version_id === V4 ? draft() : state(params.version_id ?? V3)),
    "GET /v1/methodology/versions/{version_id}/diff": ({ params, query }) => {
      const version = params.version_id ?? V3;
      if (version === V4) return json(diffOut(V4, V3, DIFF_V4_V3, 66));
      const against = query.get("against") ?? V2;
      return against === V2
        ? json(diffOut(V3, V2, DIFF_V3_V2, 54))
        : json({ detail: "against_other_template" }, 422);
    },
    "PUT /v1/methodology/versions/{version_id}/standards-mapping": ({ body }) => {
      const given = body as StandardsMappingIn;
      mapping = {
        standards_set_id: given.standards_set_id,
        quality_management_ref: given.quality_management_ref ?? null,
        engagement_types: given.engagement_types,
        default_for_new_engagements: given.default_for_new_engagements,
      };
      rowVersion += 1;
      return json(state(V3));
    },
    "GET /v1/methodology/versions/{version_id}/activity": ({ params }) => {
      const items = activity(params.version_id ?? V3);
      return json({ items, total: items.length } satisfies ListPageVersionActivityOut);
    },
    "GET /v1/methodology/versions/{version_id}/programs": () => json(programs()),
    "GET /v1/methodology/programs/{program_id}/steps": ({ params }) =>
      json(steps(params.program_id ?? "")),
    "POST /v1/methodology/versions/{version_id}/approve": ({ body }) => {
      const given = body as ApproveVersionIn;
      if (!actions.includes("approve")) return json({ detail: "forbidden" }, 403);
      if (given.checklist_hash !== HASH) return json({ detail: "checklist_changed" }, 409);
      status = "published";
      approvedAt = setup.approvedAt;
      effectiveFrom = given.effective_from;
      rowVersion += 1;
      return json(state(V3));
    },
    "POST /v1/methodology/templates/{name}/versions": () =>
      json(
        {
          detail: [
            { loc: ["body", "Steps", 14, "Level"], msg: "invalid_level", type: "invalid_level" },
          ],
        },
        422,
      ),
  };
}
