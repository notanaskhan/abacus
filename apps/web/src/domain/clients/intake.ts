// CLI-06's single-client intake (P-07-T49; docs/contracts/client-intake.md, live since
// P-07-T42), over the generated client only: the draft (autosaved on every step), dedupe, the
// per-step validation, the conflict check with its walled matches redacted, a person's clearing of
// a hit, person-recorded screening, and the one commit (Prospect only; optionally starting the
// acceptance record).

import type {
  ClientIntakeDraftOut,
  ClientIntakeDraftPayload,
  ConflictCheckOut,
  IntakeProblemOut,
  ScreeningRecordIn,
} from "@abacus/api-client";
import {
  clearConflictResultMutation,
  commitIntakeDraftMutation,
  createIntakeDraftMutation,
  dedupeMutation,
  getConflictCheckOptions,
  recordScreeningMutation,
  runConflictCheckMutation,
  updateIntakeDraftMutation,
  validateIntakeDraftMutation,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type IntakeStep = ClientIntakeDraftOut["step"];

export const INTAKE_STEPS: readonly IntakeStep[] = [
  "entity",
  "relationships",
  "contacts",
  "services",
  "conflicts",
  "review",
];

/** The step a problem's field belongs to (`entity.date_of_death` → entity). */
export function stepOfField(field: string): IntakeStep {
  const head = field.split(".")[0] ?? "";
  if (head === "entity") return "entity";
  if (head === "relationships") return "relationships";
  if (head === "contacts") return "contacts";
  if (head === "services" || head === "engagement_partner_user_id") return "services";
  if (head === "conflict_check_id") return "conflicts";
  return "review";
}

export function useConflictResults(checkId: string | null | undefined) {
  return useQuery({
    ...getConflictCheckOptions({ path: { check_id: checkId ?? "" } }),
    enabled: checkId != null,
  });
}

export function useIntakeWrites() {
  const queryClient = useQueryClient();
  const create = useMutation(createIntakeDraftMutation());
  const update = useMutation(updateIntakeDraftMutation());
  const validate = useMutation(validateIntakeDraftMutation());
  const dedupe = useMutation(dedupeMutation());
  const run = useMutation(runConflictCheckMutation());
  const clear = useMutation({
    ...clearConflictResultMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        predicate: (q) =>
          (q.queryKey[0] as { _id?: string } | undefined)?._id === "getConflictCheck",
      });
    },
  });
  const screen = useMutation(recordScreeningMutation());
  const commit = useMutation(commitIntakeDraftMutation());
  return {
    start: () => create.mutateAsync({ body: { step: "entity" } }),
    save: (draft: ClientIntakeDraftOut, step: IntakeStep, payload: ClientIntakeDraftPayload) =>
      update.mutateAsync({
        path: { draft_id: draft.id },
        body: { seen_version: draft.version, step, payload },
      }),
    validate: async (draftId: string, step: IntakeStep): Promise<IntakeProblemOut[]> =>
      (await validate.mutateAsync({ path: { draft_id: draftId }, body: { step } })).problems ?? [],
    dedupe: (name: string) => dedupe.mutateAsync({ body: { name } }),
    runCheck: (draftId: string, names: readonly string[]): Promise<ConflictCheckOut> =>
      run.mutateAsync({
        body: { names: [...names], subject: { kind: "client_intake_draft", id: draftId } },
      }),
    clearHit: (checkId: string, resultId: string, reason: string) =>
      clear.mutateAsync({
        path: { check_id: checkId, result_id: resultId },
        body: { assessment: "not_adverse", reason },
      }),
    recordScreening: (body: ScreeningRecordIn) => screen.mutateAsync({ body }),
    commit: (draftId: string, startAcceptance: boolean) =>
      commit.mutateAsync({
        path: { draft_id: draftId },
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: { start_acceptance: startAcceptance },
      }),
    busy: update.isPending || validate.isPending || commit.isPending || run.isPending,
  };
}
