// KNW-02 Methodology versions: the workbook slice's scenarios (K-01-T07; K-01 §3.3; handoff
// KNW-02 e, f). Margaret Okonkwo (QM owner) on Mon Jan 12, 2026, with `methodology.lifecycle` and
// `methodology.programs` on:
//
//   e  BH Audit Methodology · EBP v3 from the workbook, Needs review; the Approve sheet open
//      (`?ov=approve`): effective Jan 1, 2026, supersedes v2, the checklist the server computed
//   f  at 2:31 PM: approved by Margaret, v2 superseded from Dec 31, 2025; "Open program editor ›"
//   c  (K-01-T19) Diff vs v2: Added 4 · Changed 9 · Removed 1 · Unchanged 54
//   d  (K-01-T19) Standards mapping: GAAS nonissuer · AU-C 703, SQMS 1, the three EBP types, default
//   draft (K-01-T19) Hannah Leclerc reviews her v4 draft from KNW-03 c: no source file, Diff vs v3
//   a  (K-01-T23) the import of the 96-page Word file, Needs review: 3 flags; step 4 on page 14
//   a2 (K-01-T23) the ⚑ filter: step 7's range table split across pages 15–16, waiting on a confirm
//   b  (K-01-T23) 1:51 PM, Parsing: the importer is 41 pages into 96

import type { CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type FixtureRequest,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { V3, V4, methodologyHandlers } from "../handlers/methodology-versions";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();
const AT_210 = "2026-01-12T14:10:00-06:00";
const AT_231 = "2026-01-12T14:31:00-06:00";

function capabilities(persona: string | undefined): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "margaret-okonkwo");
  return {
    ...base,
    flags: {
      ...base.flags,
      "methodology.lifecycle": true,
      "methodology.programs": true,
      "methodology.import_review": true,
    },
  };
}

const AT_151 = "2026-01-12T13:51:00-06:00";
const IMPORT_FILE = "00000000-0000-4000-8000-00000000a201";
// A 1×1 transparent PNG: fixtures never ship a document; the viewer draws the page frame.
const PNG = Uint8Array.from(
  atob(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  ),
  (c) => c.charCodeAt(0),
);

function importOut(status: "needs_review" | "parsing"): Record<string, unknown> {
  return {
    id: "00000000-0000-4000-8000-00000000a200",
    template_id: "00000000-0000-4000-8000-00000000a100",
    version_id: V3,
    status,
    pages_done: status === "parsing" ? 41 : 96,
    pages_total: 96,
    failure_code: null,
    started_at: "2026-01-12T19:40:00Z",
    files: [
      {
        id: IMPORT_FILE,
        role: "document_pdf",
        filename: "BH Audit Methodology - EBP v3.pdf",
        media_type: "application/pdf",
        bytes: 1843200,
        sha256: "0".repeat(64),
        scan_status: "clean",
        created_at: "2026-01-12T19:39:00Z",
      },
      {
        id: "00000000-0000-4000-8000-00000000a202",
        role: "workbook",
        filename: "BH Audit Methodology - EBP v3.xlsx",
        media_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        bytes: 412000,
        sha256: "1".repeat(64),
        scan_status: "clean",
        created_at: "2026-01-12T19:39:00Z",
      },
    ],
  };
}

// AC7.2: 3 flags, one each in BH-EBP-110 (step 7), -310 and -410.
const FLAGGED = new Set(["BH-EBP-110", "BH-EBP-310", "BH-EBP-410"]);

function withFlags(base: FixtureHandler): FixtureHandler {
  return async (request) => {
    const response = await base(request);
    if (!response.ok) return response;
    const programs = (await response.json()) as Record<string, unknown>[];
    return json(programs.map((p) => ({ ...p, flags_open: FLAGGED.has(String(p.code)) ? 1 : 0 })));
  };
}

/** The parsed steps with their sources and the server's flags (step 4 on p. 14; step 7 split). */
function withSources(base: FixtureHandler, resolved: ReadonlySet<string>): FixtureHandler {
  return async (request) => {
    const response = await base(request);
    if (!response.ok) return response;
    const steps = (await response.json()) as Record<string, unknown>[];
    return json(
      steps.map((step) => {
        const n = step.number as number;
        const page = n === 7 ? [15, 16] : [Math.min(10 + n, 96), Math.min(10 + n, 96)];
        return {
          ...step,
          parse_flag: n === 7 ? "split_across_pages" : null,
          flag_resolution: resolved.has(String(step.id)) ? "confirmed" : null,
          sources: [
            {
              match_id: `step-${String(step.id)}-p${String(page[0])}`,
              file_id: IMPORT_FILE,
              page_from: page[0],
              page_to: page[1],
              bbox: [72, 120 + n * 8, 540, 160 + n * 8],
              quote: String(step.text).split(" ").slice(0, 6).join(" "),
              verified: true,
            },
          ],
        };
      }),
    );
  };
}

function at(
  state: string,
  status: "needs_review" | "published",
  clock: string,
  persona = "margaret-okonkwo",
  imported?: "needs_review" | "parsing",
) {
  const hannah = persona === "hannah-leclerc";
  const base = methodologyHandlers({
    status,
    approvedAt: "2026-01-12T20:31:00Z",
    ...(hannah ? { actions: ["manage"], withDraft: true } : {}),
  });
  const steps = base["GET /v1/methodology/programs/{program_id}/steps"];
  const programs = base["GET /v1/methodology/versions/{version_id}/programs"];
  const resolved = new Set<string>();
  return {
    state,
    persona,
    clock,
    handlers: {
      ...E0.handlers,
      ...base,
      "GET /v1/methodology/versions/{version_id}/import": () =>
        imported === undefined ? json({ detail: "not_found" }, 404) : json(importOut(imported)),
      ...(imported !== undefined && steps !== undefined && programs !== undefined
        ? {
            "GET /v1/methodology/versions/{version_id}/programs": withFlags(programs),
            "GET /v1/methodology/programs/{program_id}/steps": withSources(steps, resolved),
            "POST /v1/methodology/versions/{version_id}/steps/{step_id}/flag-resolution": ({
              params,
              body,
            }: FixtureRequest) => {
              const stepId = params.step_id ?? "";
              resolved.add(stepId);
              return json({
                step_id: stepId,
                step_key: "",
                parse_flag: "split_across_pages",
                resolution: "confirmed",
                text: "",
                row_version: ((body as { row_version?: number }).row_version ?? 1) + 1,
              });
            },
            "GET /v1/methodology/versions/{version_id}/files/{file_id}/pages/{page_no}": () =>
              new Response(PNG, { headers: { "content-type": "image/png" } }),
          }
        : {}),
      "GET /v1/me/capabilities": ({ persona: who }: FixtureRequest) => json(capabilities(who)),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "needs_review", AT_210, "margaret-okonkwo", "needs_review"),
  a2: at("a2", "needs_review", AT_210, "margaret-okonkwo", "needs_review"),
  b: at("b", "needs_review", AT_151, "margaret-okonkwo", "parsing"),
  c: at("c", "needs_review", AT_210),
  d: at("d", "needs_review", AT_210),
  e: at("e", "needs_review", AT_210),
  f: at("f", "published", AT_231),
  draft: at("draft", "published", "2026-10-01T10:15:00-05:00", "hannah-leclerc"),
});

export type Knw02State = keyof typeof scenarios;

/** The version and search each state opens with. */
export const OPENS: Record<
  Knw02State,
  {
    versionId: string;
    ov?: string;
    tab?: "diff" | "standards" | "activity";
    flagged?: boolean;
  }
> = {
  a: { versionId: V3 },
  a2: { versionId: V3, flagged: true },
  b: { versionId: V3 },
  c: { versionId: V3, tab: "diff" },
  d: { versionId: V3, tab: "standards" },
  e: { versionId: V3, ov: "approve" },
  f: { versionId: V3 },
  draft: { versionId: V4 },
};
