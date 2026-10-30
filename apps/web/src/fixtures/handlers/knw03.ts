// KNW-03's reads in fixture mode (K-01-T13): EBP v3 published with KNW-03's seven programs, the
// steps of BH-EBP-110 at v3 and v2 (the Change log compares them in code), the version's PBC rows,
// the step resolver the SHL-07 ↗ uses, and C4's citations of step 4 (SHL-07a's own fixture).
import type {
  CitationV2Out,
  ListPageCitationV2Out,
  MethodologyVersionOut,
  ProgramOut,
  StepResolveOut,
  TemplateVersionOut,
  VersionStateOut,
} from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { stableId } from "../seed/prng";
import {
  KNW03_ITEMS,
  KNW03_PROGRAMS,
  KNW03_STEPS_V2,
  KNW03_STEPS_V3,
} from "../seed/knw03";
import { STEP_CITATION } from "../seed/trust";
import { MARGARET, TEMPLATE, TEMPLATE_ID, V2, V3, programId } from "./methodology-versions";

function state(id: string): VersionStateOut {
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
    version: id === V2 ? 2 : 3,
    version_id: id === V2 ? V2 : V3,
    created_at: "2026-01-12T19:52:00Z",
    engagement_types: ["ebp_audit"],
  };
}

/** A program's id at a version: v3's are KNW-02's; v2's are their own (a version owns its rows). */
const programAt = (version: string, code: string): string =>
  version === V2 ? stableId(`methodology:program:v2:${code}`) : programId(code);

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
      : [];

const programById = (id: string): ProgramOut | undefined =>
  [...programs(V3), ...programs(V2)].find((p) => p.id === id);

/** Step 4's citation on AUD-04 (SHL-07a), pointed at this version's step. */
const CITED: CitationV2Out = { ...STEP_CITATION, match_id: `ms:ebp-110-4@v3` };

export function knw03Handlers(): Record<string, FixtureHandler> {
  return {
    "GET /v1/methodology/templates": () => json([summary(V3), summary(V2)]),
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
      json(stepsOf(params.program_id ?? "")),
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
