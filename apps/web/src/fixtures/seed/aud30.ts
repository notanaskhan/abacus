// AUD-30 Post-issuance (Q-05-T24; TASK-8934; DEC-5936): Northwind Robotics 401(k) Plan's two
// cases, PI-02's memo addition and PI-01's analysis, exported from the Python quality slice
// (`quality_slice.aud30_rows`, `scenario.aud30.json`); every figure is the code's there (PI-01's
// comparison and evaluation). This file only derives the decided states the artboards show:
// b (no action, the addition logged), c (revise and reissue) and the new case (f).
import type {
  ArchiveAdditionOut,
  PostIssuanceAnalysisOut,
  PostIssuanceCaseIn,
  PostIssuanceCaseOut,
  PostIssuanceDecisionIn,
} from "@abacus/api-client";
import exported from "./scenario.aud30.json";
import { stableId } from "./prng";

const DATA = exported as unknown as {
  archive_locked_at: string;
  cases: PostIssuanceCaseOut[];
  additions: ArchiveAdditionOut[];
  analysis: PostIssuanceAnalysisOut & { run_number: number };

  next_addition_sha: string;
};

export const AUD30_LOCKED_AT = DATA.archive_locked_at;
export const AUD30_RUN_NUMBER = DATA.analysis.run_number;
export const MARGARET = "Margaret Okonkwo";
export const MARGARET_ID = stableId("user:MO");

/** The artboards' clock: Mon Jan 25, 2027, 9:24 AM CT. */
export const AUD30_CLOCK = "2027-01-25T09:24:00-06:00";
const DECIDED_AT = "2027-01-25T15:24:00Z";

export type Aud30Decided = "no_action" | "revise_and_reissue" | null;

export function cases(decided: Aud30Decided = null): PostIssuanceCaseOut[] {
  return DATA.cases.map((c) =>
    c.ref !== "PI-01" || decided === null
      ? c
      : {
          ...c,
          status: decided === "no_action" ? "concluded_no_action" : "reissue_in_progress",
          decision: decided,
          decided_by_user_id: MARGARET_ID,
          decided_by_name: MARGARET,
          decided_at: DECIDED_AT,
          rationale:
            decided === "no_action"
              ? "Below clearly trivial; no note or schedule total changes. Documented and logged."
              : "Management will revise the statements for the corrected Stable Value Fund figure, and we will reissue a dual-dated report.",
        },
  );
}

/** A decision as the server records it: the case decided, and (with a source) its addition. */
export function decide(
  all: PostIssuanceCaseOut[],
  caseId: string,
  body: PostIssuanceDecisionIn,
): PostIssuanceCaseOut | undefined {
  const found = all.find((c) => c.case_id === caseId);
  if (found === undefined) return undefined;
  return {
    ...found,
    status:
      body.decision === "no_action"
        ? "concluded_no_action"
        : body.decision === "revise_and_reissue"
          ? "reissue_in_progress"
          : "concluded",
    decision: body.decision,
    decided_by_user_id: MARGARET_ID,
    decided_by_name: MARGARET,
    decided_at: DECIDED_AT,
    rationale: body.rationale,
  };
}

/** The additions the archive holds; b gains PI-01's pending addition ("Addition logged"). */
export function additions(withPi01: string | null = null): ArchiveAdditionOut[] {
  const pi01 = DATA.cases.find((c) => c.ref === "PI-01");
  if (withPi01 === null || pi01 === undefined) return DATA.additions;
  return [
    ...DATA.additions,
    {
      id: stableId("addition:PI-01"),
      description: withPi01,
      reason_code: "au_c_560_subsequently_discovered_fact",
      evidence_version_id: pi01.source_evidence_version_id ?? stableId("pi01-source"),
      content_sha256: DATA.next_addition_sha,
      added_by_name: MARGARET,
      added_at: DECIDED_AT,
      decision: "pending",
      decided_by_name: null,
      decided_at: null,
      post_issuance_case_id: pi01.case_id,
    },
  ];
}

export function analysis(): PostIssuanceAnalysisOut {
  const a = DATA.analysis;
  return {
    case_id: a.case_id,
    run_id: a.run_id,
    blocks: a.blocks,
    recommendation: a.recommendation ?? null,
    citation_ids: a.citation_ids ?? [],
    run_number: a.run_number,
  };
}

/** f: a new case as the server opens it (PI-03, under evaluation, no comparison yet). */
export function opened(body: PostIssuanceCaseIn): PostIssuanceCaseOut {
  return {
    case_id: stableId("PI-03"),
    ref: "PI-03",
    type: body.type,
    standard:
      body.type === "subsequently_discovered_facts"
        ? "au_c_560"
        : body.type === "omitted_procedure"
          ? "au_c_585"
          : null,
    source_kind: body.source_kind,
    received_at: DECIDED_AT,
    description: body.description,
    status: "under_evaluation",
    comparison: [],
    evaluation: null,
    options: body.type === "omitted_procedure" ? ["no_action", "revise_and_reissue"] : [],
    raised_by_name: MARGARET,
    opened_at: DECIDED_AT,
    allowed_actions: DATA.cases[0]?.allowed_actions ?? [],
  };
}
