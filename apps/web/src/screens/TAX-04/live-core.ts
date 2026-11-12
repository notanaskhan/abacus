// T-04-T29 (TASK-6828): the review workspace's live plumbing, shared by TAX-04, TAX-05, TAX-06,
// TAX-07 and TXI-01 on a live build (fixture builds keep the artboards).
//
// - Counts on a second tab: the return's engagement topic (`engagement:<id>` on `GET /v1/events`)
//   refetches the workspace summary and the sections' reads when a document is approved or
//   unapproved, an issue moves, a checkpoint is recorded or decided, or a section is signed off
//   (`document_approval.changed`, `issue.status_changed`, `checkpoint.*`, `sign_off.recorded`;
//   notifications/realtime.py). With `realtime.sse` off, or after three failed connections, every
//   read polls instead (`useRealtimeInterval`, the permanent fallback).
// - Every 409 (and the 403 level refusal) renders its blocker in words (`blockerWords`), never a
//   code; an unknown code reads as the generic sentence.

import type { QueryKey } from "@tanstack/react-query";
import { useRealtimeInterval, useRealtimeStream } from "../../app-core/realtime-hooks";
import { registerTopicKeys } from "../../app-core/realtime";

/** The reads an engagement event refetches (generated keys match on `_id`). */
export const RETURN_LIVE_KEYS: readonly QueryKey[] = [
  "workspace",
  "returnRecord",
  "reviewTree",
  "worksheets",
  "worksheetFields",
  "issueList",
  "issue",
  "checkpointHistory",
  "signOffLadder",
  "signOffEligibility",
  "engagementActivity",
].map((id) => [{ _id: id }]);

registerTopicKeys("engagement", () => RETURN_LIVE_KEYS);

/** Subscribe the tab to the return's engagement; answers the reads' `refetchInterval`. */
export function useReturnLive(engagementId: string | undefined): number | false {
  useRealtimeStream(engagementId === undefined ? [] : [`engagement:${engagementId}`]);
  return useRealtimeInterval("record");
}

export const BLOCKER_COPY = {
  // TAX-04 c (handoff spec): the footer helper while a mismatch stands (the tree's state).
  mismatch: (n: number) => `Resolve ${String(n)} mismatch${n === 1 ? "" : "es"} to approve`,
  version_superseded: "A newer version of this document arrived. Review it, then approve.",
  level_not_permitted: "Your review level cannot approve at this level.",
  already_reversed: "This approval was already removed.",
  draft_k1: "The K-1 is still a draft. Final approval waits for the released K-1.",
  blocking_issues: "Open issues block final approval. Resolve them on the Issues tab.",
  unapproved_documents: "Some documents are not approved yet at manager level.",
  issue_changed: "Someone changed this issue. It has been reloaded; try again.",
  issue_status_refused: "This issue cannot move from its current status.",
  system_resolved_only: "This issue resolves when the final K-1 is released.",
  field_changed: "This field changed since you opened it. It has been reloaded; try again.",
  content_changed: "The section changed since you opened it. Review it again, then sign off.",
  proposal_changed: "The proposal changed since you opened it. It has been reloaded.",
  undo_window_closed: "Undo is no longer available.",
  effect_started: "Undo is no longer available: the change has already been applied.",
  generic: "That did not go through. Reload and try again.",
} as const;

type Sentence = Exclude<keyof typeof BLOCKER_COPY, "mismatch">;

interface ApiProblem {
  detail?: unknown;
  facts?: { blockers?: unknown } | null;
}

function sentence(code: string): string {
  // TASK-7330 (AC-1.4): a forced approve of a mismatched document answers 409 `mismatch`.
  if (code === "mismatch") return BLOCKER_COPY.mismatch(1);
  return code in BLOCKER_COPY ? BLOCKER_COPY[code as Sentence] : BLOCKER_COPY.generic;
}

/** The words for a refusal: one sentence per blocker, in the server's order. The final-approval
 * refusal (`final_approval_blocked`) names its blockers comma-joined in `facts.blockers`. */
export function blockerWords(error: unknown): string[] {
  const e = (error ?? {}) as ApiProblem;
  const raw = e.facts?.blockers;
  const blockers =
    typeof raw === "string"
      ? raw.split(",").filter((b) => b !== "")
      : Array.isArray(raw)
        ? raw.filter((b): b is string => typeof b === "string")
        : [];
  if (blockers.length > 0) return blockers.map(sentence);
  return [sentence(typeof e.detail === "string" ? e.detail : "")];
}
