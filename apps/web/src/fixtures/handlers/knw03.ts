// KNW-03's reads in fixture mode (K-01-T13): EBP v3 published with KNW-03's seven programs, the
// steps of BH-EBP-110 at v3 and v2 (the Change log compares them in code), the version's PBC rows,
// the step resolver the SHL-07 ↗ uses, and C4's citations of step 4 (SHL-07a's own fixture).
import type {
  AbacusModulesMethodologyContractStepOut as StepOut,
  CitationV2Out,
  ListPageCitationV2Out,
  MethodologyVersionOut,
  ProgramOut,
  RunViewOut,
  StepCreateIn,
  StepPatchIn,
  StepResolveOut,
  TemplateVersionOut,
  VersionStateOut,
} from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { stableId } from "../seed/prng";
import {
  KNW03_ITEMS,
  KNW03_PROGRAMS,
  KNW03_RUN,
  KNW03_STEPS_140,
  KNW03_STEPS_V4,
  KNW03_STEPS_V2,
  KNW03_STEPS_V3,
  KNW03_STEP4_QUOTE,
} from "../seed/knw03";
import { STEP_CITATION } from "../seed/trust";
import { MARGARET, TEMPLATE, TEMPLATE_ID, V2, V3, programId } from "./methodology-versions";

/** c: Hannah Leclerc's draft v4, drafted from v3 (K-01-T15). */
export const V4 = stableId("methodology:version:ebp-v4-draft");

function state(id: string): VersionStateOut {
  if (id === V4) {
    return {
      ...state(V3),
      version_id: V4,
      label: "v4 draft",
      status: "draft",
      approval_basis: null,
      approved_at: null,
      approved_by_name: null,
      approved_by_user_id: null,
      effective_from: null,
      default_for_new_engagements: false,
      drafted_from_version_id: V3,
      row_version: 3,
      allowed_actions: ["export", "methodology.edit", "methodology.submit", "methodology.discard"],
    };
  }
  const v3 = id !== V2;
  return {
    version_id: v3 ? V3 : V2,
    template_id: TEMPLATE_ID,
    label: v3 ? "v3" : "v2",
    status: v3 ? "published" : "superseded",
    approval_basis: "approved",
    approved_at: v3 ? "2026-01-12T20:31:00Z" : "2025-01-14T16:05:00Z",
    approved_by_name: MARGARET.name,
    approved_by_user_id: MARGARET.user_id,
    effective_from: v3 ? "2026-01-01" : "2025-01-01",
    effective_to: v3 ? null : "2025-12-31",
    default_for_new_engagements: v3,
    drafted_from_version_id: null,
    engagement_types: ["ebp_audit"],
    standards_set_id: null,
    row_version: 2,
    allowed_actions: ["export"],
  };
}

function summary(id: string): TemplateVersionOut {
  return {
    template_id: TEMPLATE_ID,
    template_name: TEMPLATE,
    version: id === V2 ? 2 : id === V4 ? 4 : 3,
    version_id: id === V2 ? V2 : id === V4 ? V4 : V3,
    created_at: "2026-01-12T19:52:00Z",
    engagement_types: ["ebp_audit"],
  };
}

/** A program's id at a version: v3's are KNW-02's; v2's are their own (a version owns its rows). */
const programAt = (version: string, code: string): string =>
  version === V2
    ? stableId(`methodology:program:v2:${code}`)
    : version === V4
      ? stableId(`methodology:program:v4:${code}`)
      : programId(code);
/** c opens BH-EBP-110 at the v4 draft. */
export const DRAFT_110 = stableId("methodology:program:v4:BH-EBP-110");

function programs(id: string): ProgramOut[] {
  return KNW03_PROGRAMS.map(([code, name, steps, mandatory], n) => ({
    id: programAt(id, code),
    version: state(id),
    code,
    name,
    position: n + 1,
    // v2's BH-EBP-110 had no step 15.
    step_count: id === V2 && code === "BH-EBP-110" ? steps - 1 : steps,
    mandatory_count: mandatory,
    flags_open: 0,
    counts_by_level: {},
  }));
}

const stepsOf = (program: string) =>
  program === programAt(V3, "BH-EBP-110")
    ? KNW03_STEPS_V3
    : program === programAt(V2, "BH-EBP-110")
      ? KNW03_STEPS_V2
      : program === programAt(V4, "BH-EBP-110")
        ? KNW03_STEPS_V4
        : program === programAt(V3, "BH-EBP-140")
          ? KNW03_STEPS_140
          : [];

const programById = (id: string): ProgramOut | undefined =>
  [...programs(V3), ...programs(V2), ...programs(V4)].find((p) => p.id === id);

/** Step 4's citation on AUD-04 (SHL-07a), pointed at this version's step, quoting the step as
 * KNW-03 b draws it (the SHL-07 and KNW-03 handoffs word step 4 differently; each screen keeps its
 * own artboard's words). */
const CITED: CitationV2Out = {
  ...STEP_CITATION,
  quote: KNW03_STEP4_QUOTE,
  match_id: `ms:ebp-110-4@v3`,
};

export function knw03Handlers(): Record<string, FixtureHandler> {
  // c's writes on the v4 draft (K-01-T14's routes): the person's edits stand for the walk.
  const added: StepOut[] = [];
  const removed = new Set<string>();
  const edited = new Map<string, StepOut>();
  const draftSteps = (): StepOut[] => [
    ...KNW03_STEPS_V4.filter((s) => !removed.has(s.id)).map((s) => edited.get(s.id) ?? s),
    ...added,
  ];
  return {
    "GET /v1/methodology/templates": () => json([summary(V4), summary(V3), summary(V2)]),
    "GET /v1/methodology/versions/{version_id}": ({ params }) =>
      json({
        summary: summary(params.version_id ?? V3),
        areas: [],
        items: KNW03_ITEMS,
        rules: [],
      } satisfies MethodologyVersionOut),
    "GET /v1/methodology/versions/{version_id}/state": ({ params }) =>
      json(state(params.version_id ?? V3)),
    "GET /v1/methodology/versions/{version_id}/programs": ({ params }) =>
      json(programs(params.version_id ?? V3)),
    "GET /v1/methodology/programs/{program_id}": ({ params }) => {
      const found = programById(params.program_id ?? "");
      return found === undefined ? json({ detail: "not_found" }, 404) : json(found);
    },
    "GET /v1/methodology/programs/{program_id}/steps": ({ params }) =>
      json(params.program_id === DRAFT_110 ? draftSteps() : stepsOf(params.program_id ?? "")),
    "POST /v1/methodology/versions/{version_id}/programs/{program_id}/steps": ({ body }) => {
      const input = body as StepCreateIn;
      const n = draftSteps().length + 1;
      const step: StepOut = {
        ...(KNW03_STEPS_V4[0] ?? (undefined as never)),
        id: stableId(`methodology:step:110:v4:new:${String(n)}`),
        step_key: `ebp-110-${String(n)}`,
        anchor: `ebp-110-${String(n)}@v4`,
        number: n,
        text: input.text,
        assertions: input.assertions ?? [],
        standard_refs: input.standard_refs ?? [],
        level: input.level,
        mandatory: false,
        lock_note: null,
        guidance: [],
        prepopulates: [],
        pbc_positions: [],
        origin: "manual",
        allowed_actions: ["methodology.edit_step", "methodology.remove_step"],
      };
      added.push(step);
      return json(step, 201);
    },
    "PATCH /v1/methodology/versions/{version_id}/steps/{step_id}": ({ params, body }) => {
      const id = params.step_id ?? "";
      const base = draftSteps().find((s) => s.id === id);
      if (base === undefined) return json({ detail: "not_found" }, 404);
      const patch = body as StepPatchIn;
      const next: StepOut = {
        ...base,
        ...(patch.text == null ? {} : { text: patch.text }),
        row_version: base.row_version + 1,
      };
      edited.set(id, next);
      return json(next);
    },
    "DELETE /v1/methodology/versions/{version_id}/steps/{step_id}": ({ params }) => {
      removed.add(params.step_id ?? "");
      return new Response(null, { status: 204 });
    },
    "POST /v1/methodology/versions/{version_id}/submit": () =>
      json({ ...state(V4), status: "needs_review", allowed_actions: ["export"] }),
    // f: the failed Internal Control run (C6 v1) the Fix in Knowledge arrival quotes.
    "GET /v1/agent-runs/{run_id}": ({ params }) =>
      params.run_id === KNW03_RUN.id
        ? json({
            run: KNW03_RUN,
            projection: "metadata",
            allowed_actions: [],
            run_record_sha256: `sha256:${"0".repeat(64)}`,
          } satisfies RunViewOut)
        : json({ detail: "not_found" }, 404),
    // K-01-T12's deterministic export; the fixture answers an empty workbook body.
    "GET /v1/methodology/versions/{version_id}/export.xlsx": () =>
      new Response(new Blob([]), {
        headers: {
          "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          "Content-Disposition": 'attachment; filename="BH-Audit-Methodology-EBP-v3.xlsx"',
        },
      }),
    "GET /v1/methodology/steps/resolve": ({ query }) => {
      const key = query.get("key") ?? "";
      const step = KNW03_STEPS_V3.find((s) => s.step_key === key);
      if (step === undefined) return json({ detail: "not_found" }, 404);
      return json({
        anchor: step.anchor,
        number: step.number,
        program_code: "BH-EBP-110",
        program_id: programId("BH-EBP-110"),
        step_id: step.id,
        version_id: V3,
      } satisfies StepResolveOut);
    },
    "GET /v1/citations": ({ query }) => {
      const items =
        query.get("kind") === "methodology_step" && query.get("anchor_ref") === "ebp-110-4@v3"
          ? [CITED]
          : [];
      return json({ items, total: items.length } satisfies ListPageCitationV2Out);
    },
  };
}
