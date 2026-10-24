// Follow-ups v2 (P-06-T14, P-06-T16; C5 v1.2 §12): the platform drafts one follow-up per client
// contact from the firm's published Reminder template, a person edits and sends them, and Undo
// takes them back within ten seconds (ADR-161). The agent never sends (DEC-74): every write here
// is the signed-in person's.

import type { FollowUpOut } from "@abacus/api-client";
import {
  draftSelectionFollowUpsMutation,
  editFollowUpMutation,
  sendFollowUpsMutation,
  undoFollowUpMutation,
} from "@abacus/api-client/query";
import { useMutation, useQueryClient } from "@tanstack/react-query";

export type FollowUp = FollowUpOut;

/** What a draft is asked for: the binders BND-01 selected, or one binder's open requests. */
export type FollowUpSelection =
  | { kind: "binders"; binderIds: readonly string[] }
  | { kind: "requests"; requestItemIds: readonly string[] };

function idempotencyKey(): string {
  return globalThis.crypto.randomUUID();
}

function useRefreshRequests(): () => void {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({
      predicate: (q) => {
        const id = (q.queryKey[0] as { _id?: string } | undefined)?._id ?? "";
        return id === "listBinders" || id === "binderRequests" || id === "getBinder";
      },
    });
  };
}

/** Draft, edit, send (all at once, one Idempotency-Key) and Undo. */
export function useFollowUps() {
  const refresh = useRefreshRequests();
  const draft = useMutation({ ...draftSelectionFollowUpsMutation() });
  const edit = useMutation({ ...editFollowUpMutation() });
  const send = useMutation({ ...sendFollowUpsMutation(), onSuccess: refresh });
  const undo = useMutation({ ...undoFollowUpMutation(), onSuccess: refresh });
  return {
    draft: async (selection: FollowUpSelection): Promise<FollowUp[]> => {
      const body =
        selection.kind === "binders"
          ? { binder_ids: [...selection.binderIds] }
          : { request_item_ids: [...selection.requestItemIds] };
      return (await draft.mutateAsync({ body })).items;
    },
    edit: (id: string, body: string): Promise<FollowUp> =>
      edit.mutateAsync({ path: { follow_up_id: id }, body: { body } }),
    send: async (ids: readonly string[]): Promise<FollowUp[]> =>
      (
        await send.mutateAsync({
          body: { ids: [...ids] },
          headers: { "Idempotency-Key": idempotencyKey() },
        })
      ).items,
    undo: (id: string): Promise<FollowUp> => undo.mutateAsync({ path: { follow_up_id: id } }),
    drafting: draft.isPending,
    sending: send.isPending,
  };
}
