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

import type { CapabilitiesOut } from "@abacus/api-client";
import { type FixtureRequest, defineScenarios, json } from "../../app-core/fixture-mode";
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

function at(
  state: string,
  status: "needs_review" | "published",
  clock: string,
  persona = "margaret-okonkwo",
) {
  const hannah = persona === "hannah-leclerc";
  return {
    state,
    persona,
    clock,
    handlers: {
      ...E0.handlers,
      ...methodologyHandlers({
        status,
        approvedAt: "2026-01-12T20:31:00Z",
        ...(hannah ? { actions: ["manage"], withDraft: true } : {}),
      }),
      "GET /v1/me/capabilities": ({ persona: who }: FixtureRequest) => json(capabilities(who)),
    },
  };
}

export const scenarios = defineScenarios({
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
  { versionId: string; ov?: string; tab?: "diff" | "standards" | "activity" }
> = {
  c: { versionId: V3, tab: "diff" },
  d: { versionId: V3, tab: "standards" },
  e: { versionId: V3, ov: "approve" },
  f: { versionId: V3 },
  draft: { versionId: V4 },
};
