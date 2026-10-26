// CLI-07's acceptance record (P-07-T46; docs/contracts/acceptance-independence.md, live since
// P-07-T35), over the generated client only: the record, the review picker's people, and the
// writes a person makes — ask for and complete a manual check, add a flag, send to the partner,
// request and complete the risk-partner review, decide, and complete a condition. Every write
// reads the record (and the engagement, whose status the decision moves) again. The server's
// refusals are the screen's to say; a stale MFA on the decision is the shell's step-up.

import type { AcceptanceRecordOut, AcceptanceSectionOut } from "@abacus/api-client";
import {
  addAcceptanceFlagMutation,
  completeConditionMutation,
  completeManualCheckMutation,
  completeRiskPartnerReviewMutation,
  decideAcceptanceMutation,
  engagementRecordQueryKey,
  getAcceptanceOptions,
  getAcceptanceQueryKey,
  requestManualCheckMutation,
  requestRiskPartnerReviewMutation,
  sendToPartnerMutation,
  teamCandidatesOptions,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type AcceptanceOption = NonNullable<AcceptanceRecordOut["decision"]>["option"];
export type FlagSeverity = NonNullable<AcceptanceRecordOut["flags"]>[number]["severity"];

const path = (engagementId: string) => ({ path: { engagement_id: engagementId } });

/** `GET …/acceptance`: the record with its sections, flags, decision and `allowed_actions`. */
export function useAcceptance(engagementId: string) {
  return useQuery({ ...getAcceptanceOptions(path(engagementId)), retry: false });
}

/** The people "Request risk-partner review…" offers (the engagement's add candidates: active,
 * unwalled staff not on the team; the server admits only a partner-level one). */
export function useReviewCandidates(engagementId: string, enabled: boolean) {
  return useQuery({ ...teamCandidatesOptions(path(engagementId)), retry: false, enabled });
}

export interface NewCondition {
  text: string;
  assigneeUserId: string;
}

/** The record's writes; each reads the record and its engagement again. */
export function useAcceptanceWrites(engagementId: string) {
  const queryClient = useQueryClient();
  const refresh = async (): Promise<void> => {
    await Promise.all(
      [
        getAcceptanceQueryKey(path(engagementId)),
        engagementRecordQueryKey(path(engagementId)),
      ].map((queryKey) => queryClient.invalidateQueries({ queryKey })),
    );
  };
  const request = useMutation({ ...requestManualCheckMutation(), onSuccess: refresh });
  const complete = useMutation({ ...completeManualCheckMutation(), onSuccess: refresh });
  const flag = useMutation({ ...addAcceptanceFlagMutation(), onSuccess: refresh });
  const send = useMutation({ ...sendToPartnerMutation(), onSuccess: refresh });
  const review = useMutation({ ...requestRiskPartnerReviewMutation(), onSuccess: refresh });
  const reviewed = useMutation({ ...completeRiskPartnerReviewMutation(), onSuccess: refresh });
  const decide = useMutation({ ...decideAcceptanceMutation(), onSuccess: refresh });
  const condition = useMutation({ ...completeConditionMutation(), onSuccess: refresh });
  const at = (sectionCode: string) => ({
    path: { engagement_id: engagementId, section_code: sectionCode },
  });
  return {
    requestCheck: (sectionCode: string, userId: string) =>
      request.mutateAsync({ ...at(sectionCode), body: { requested_of: userId } }),
    completeCheck: (sectionCode: string, note: string) =>
      complete.mutateAsync({ ...at(sectionCode), body: { note: note.trim() || null } }),
    addFlag: (title: string, severity: FlagSeverity, body: string) =>
      flag.mutateAsync({ ...path(engagementId), body: { title, severity, body, sources: [] } }),
    send: (seenVersion: number) =>
      send.mutateAsync({ ...path(engagementId), body: { seen_version: seenVersion } }),
    requestReview: (partnerId: string) =>
      review.mutateAsync({ ...path(engagementId), body: { partner_id: partnerId } }),
    completeReview: () => reviewed.mutateAsync({ ...path(engagementId), body: {} }),
    decide: (
      option: AcceptanceOption,
      rationale: string,
      conditions: readonly NewCondition[],
      seenVersion: number,
    ) =>
      decide.mutateAsync({
        ...path(engagementId),
        body: {
          option,
          rationale,
          seen_version: seenVersion,
          conditions: conditions.map((c) => ({
            text: c.text,
            assignee_user_id: c.assigneeUserId,
          })),
        },
      }),
    completeCondition: (conditionId: string) =>
      condition.mutateAsync({
        path: { engagement_id: engagementId, condition_id: conditionId },
        body: {},
      }),
    pending:
      request.isPending ||
      complete.isPending ||
      flag.isPending ||
      send.isPending ||
      review.isPending ||
      reviewed.isPending ||
      decide.isPending ||
      condition.isPending,
  };
}

/** The record's `allowed_actions` hold the action. */
export function mayOn(record: AcceptanceRecordOut | undefined, action: string): boolean {
  return (record?.allowed_actions ?? []).includes(action);
}

/** Decided or declined: everything reads, nothing writes (the record is locked). */
export function isLocked(record: AcceptanceRecordOut): boolean {
  return record.status === "decided" || record.status === "declined";
}

/** The sections with a manual check still open. */
export function openChecks(record: AcceptanceRecordOut): AcceptanceSectionOut[] {
  return (record.sections ?? []).filter((s) => s.answer_state === "manual_check_open");
}

/** The conclusion is the partner's; it is not an answer the preparer gives. */
export const CONCLUSION = "conclusion";

/** Sections still unanswered, apart from the conclusion: the questionnaire is in progress. */
export function unanswered(record: AcceptanceRecordOut): AcceptanceSectionOut[] {
  return (record.sections ?? []).filter(
    (s) => s.code !== CONCLUSION && s.answer_state === "pending",
  );
}

/** Answered with no flag: complete, or confirmed by a manual check. */
export function isClear(s: AcceptanceSectionOut): boolean {
  return s.answer_state === "complete" || s.answer_state === "manual_check_done";
}

/** A text answer of a section (`summary`, `detail`), when the template asked for one. */
export function answerText(s: AcceptanceSectionOut, key: string): string | null {
  const v = s.answers?.[key];
  return typeof v === "string" && v !== "" ? v : null;
}

/** The server's refusal code (`detail`), when the error is one. */
export function refusalOf(error: unknown): string | null {
  const detail = (error as { detail?: unknown } | null)?.detail;
  return typeof detail === "string" ? detail : null;
}

/** The field a 422 names (`facts.field`). */
export function fieldOf(error: unknown): string | null {
  const field = (error as { facts?: { field?: unknown } } | null)?.facts?.field;
  return typeof field === "string" ? field : null;
}

/** A 403 that asks for a fresh sign-in (ADR-030): `facts.reason` `mfa_required`, or the plain
 * `forbidden` the matrix's `mfa_recent` answers for someone who otherwise holds the action. */
export function needsStepUp(error: unknown): boolean {
  const e = error as { detail?: unknown; facts?: { reason?: unknown } } | null;
  return e?.facts?.reason === "mfa_required" || e?.detail === "forbidden";
}
