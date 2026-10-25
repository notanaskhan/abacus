// SHL-20 reads and writes (P-06-T22; C5 v1.2 §12), through the generated client only. The card is
// polled every 2 s while a rerun runs (DEC-23 polling first). Every write is the signed-in
// person's: rerun, feedback, the screening-return draft, its edit and send, and the send-back
// (the agent never returns, sends or accepts; INV-1).

import type {
  CitationV2Out,
  FollowUpOut,
  ScreeningCardOut,
  ScreeningFeedbackIn,
} from "@abacus/api-client";
import {
  draftScreeningReturnMutation,
  editFollowUpMutation,
  getCitationOptions,
  rerunScreeningMutation,
  screeningCardOptions,
  screeningFeedbackMutation,
  sendFollowUpMutation,
  undoFollowUpMutation,
} from "@abacus/api-client/query";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

/** DEC-23: a running screening is asked again every 2 s. */
export const SCREENING_POLL_MS = 2000;

export function pollWhileRunning(card: ScreeningCardOut | undefined): number | false {
  return card?.running === true ? SCREENING_POLL_MS : false;
}

export interface ScreeningSubjectRef {
  engagementId: string;
  itemId: string;
}

export function useScreeningCard(subject: ScreeningSubjectRef | null) {
  return useQuery({
    ...screeningCardOptions({
      path: {
        engagement_id: subject?.engagementId ?? "",
        item_id: subject?.itemId ?? "",
      },
    }),
    enabled: subject !== null,
    refetchInterval: (query) => pollWhileRunning(query.state.data),
  });
}

/** The flags' verified citations (`region_ref`): each reason and the region "View" lights. */
export function useFlagCitations(ids: readonly string[]): Record<string, CitationV2Out> {
  const results = useQueries({
    queries: ids.map((id) => getCitationOptions({ path: { citation_id: id } })),
  });
  const out: Record<string, CitationV2Out> = {};
  results.forEach((r, i) => {
    const id = ids[i];
    if (id !== undefined && r.data !== undefined) out[id] = r.data;
  });
  return out;
}

function idempotencyKey(): string {
  return globalThis.crypto.randomUUID();
}

export function useScreeningWrites(subject: ScreeningSubjectRef | null) {
  const queryClient = useQueryClient();
  const refresh = (): void => {
    void queryClient.invalidateQueries({
      predicate: (q) => {
        const id = (q.queryKey[0] as { _id?: string } | undefined)?._id ?? "";
        return id === "screeningCard" || id === "binderRequests" || id === "getBinder";
      },
    });
  };
  const rerun = useMutation({ ...rerunScreeningMutation(), onSuccess: refresh });
  const feedback = useMutation({ ...screeningFeedbackMutation(), onSuccess: refresh });
  const draft = useMutation({ ...draftScreeningReturnMutation() });
  const edit = useMutation({ ...editFollowUpMutation() });
  const send = useMutation({ ...sendFollowUpMutation(), onSuccess: refresh });
  const undo = useMutation({ ...undoFollowUpMutation(), onSuccess: refresh });
  const path = {
    engagement_id: subject?.engagementId ?? "",
    item_id: subject?.itemId ?? "",
  };
  return {
    rerun: () => rerun.mutateAsync({ path }),
    rerunning: rerun.isPending,
    feedback: (resultId: string, body: ScreeningFeedbackIn) =>
      feedback.mutateAsync({ path: { screening_result_id: resultId }, body }),
    draftReturn: (returning: readonly string[]): Promise<FollowUpOut> =>
      draft.mutateAsync({
        path,
        body: {
          kind: "screening_return",
          returning: [...returning],
          reason_code: "wrong_document",
        },
      }),
    edit: (id: string, body: string): Promise<FollowUpOut> =>
      edit.mutateAsync({ path: { follow_up_id: id }, body: { body } }),
    send: (id: string): Promise<FollowUpOut> =>
      send.mutateAsync({
        path: { follow_up_id: id },
        headers: { "Idempotency-Key": idempotencyKey() },
      }),
    sending: send.isPending,
    undo: (id: string): Promise<FollowUpOut> => undo.mutateAsync({ path: { follow_up_id: id } }),
  };
}
