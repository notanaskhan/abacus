// KNW-02's workbook slice in fixture mode (K-01-T07; K-01 §3.3, §4): BH Audit Methodology · EBP v3
// imported from the workbook, in Needs review, its seven programs and BH-EBP-110's parsed steps,
// the approval checklist the server computes, approve (supersedes v2) and the workbook upload with
// its row problems. Program reads are K-01-T12's (stubbed on main); here they answer from the
// handoff's figures: 16 + 8 + 6 + 8 + 10 + 7 + 12 = 67 steps.

import type {
  AbacusModulesMethodologyContractStepOut as StepOut,
  ApproveVersionIn,
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

export interface MethodologySetup {
  status: "needs_review" | "published";
  /** Instants the approval stamps (f: 2:31 PM). */
  approvedAt: string;
  /** What the persona may do (Margaret: approve; Hannah: manage only). */
  actions?: readonly string[];
}

export function methodologyHandlers(setup: MethodologySetup): Record<string, FixtureHandler> {
  let status: VersionStateOut["status"] = setup.status;
  let approvedAt: string | null = setup.status === "published" ? setup.approvedAt : null;
  let effectiveFrom: string | null = setup.status === "published" ? "2026-01-01" : null;
  let rowVersion = setup.status === "published" ? 2 : 1;
  const actions = setup.actions ?? ["approve", "manage"];

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
          default_for_new_engagements: status === "published",
          drafted_from_version_id: null,
          engagement_types: ["ebp_audit"],
          standards_set_id: null,
          row_version: rowVersion,
          checklist: [
            { code: "has_programs", ok: true, n: PROGRAMS.length },
            { code: "has_steps", ok: true, n: 67 },
            { code: "every_program_has_steps", ok: true, n: 0 },
          ],
          checklist_hash: HASH,
          allowed_actions: status === "needs_review" ? [...actions] : [],
        };

  const summary = (id: string): TemplateVersionOut => ({
    template_id: TEMPLATE_ID,
    template_name: TEMPLATE,
    version: id === V2 ? 2 : 3,
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
    "GET /v1/methodology/templates": () => json([summary(V3), summary(V2)]),
    "GET /v1/methodology/versions/{version_id}": ({ params }) =>
      json({
        summary: summary(params.version_id ?? V3),
        areas: [],
        items: [],
        rules: [],
      } satisfies MethodologyVersionOut),
    "GET /v1/methodology/versions/{version_id}/state": ({ params }) =>
      json(state(params.version_id ?? V3)),
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
