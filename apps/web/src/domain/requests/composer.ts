// The request composer's reads and writes (P-06 §5.2, L3; SHL-14; docs/contracts/
// c5-requests-binders.md) over the generated client only. A new request is created with the
// live body (`audit_area`, `description`), then given its fields by the v2 PATCH; sending is its
// own person's act with an Idempotency-Key. The server refuses a send without a due date (422
// `due_date_required`) and a model-worded draft while P-25 is off (409
// `model_text_not_permitted`); the screen says both.

import type { RequestItemPatchIn, RequestItemV2Out } from "@abacus/api-client";
import {
  clientContactsOptions,
  createRequestItemMutation,
  delegateRequestItemMutation,
  incorporateRequestItemMutation,
  itemCommentsOptions,
  listRequestItemsOptions,
  sendRequestItemMutation,
  updateRequestItemMutation,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export function useClientContacts(engagementId: string | undefined) {
  return useQuery({
    ...clientContactsOptions({ path: { engagement_id: engagementId ?? "" } }),
    enabled: engagementId !== undefined,
    retry: false,
  });
}

/** The engagement's request items (C1 v1): the description and client assignee of one. */
export function useRequestItems(engagementId: string | undefined) {
  return useQuery({
    ...listRequestItemsOptions({ path: { engagement_id: engagementId ?? "" } }),
    enabled: engagementId !== undefined,
    retry: false,
  });
}

export function useItemComments(engagementId: string | undefined, itemId: string | null) {
  return useQuery({
    ...itemCommentsOptions({
      path: { engagement_id: engagementId ?? "", item_id: itemId ?? "" },
    }),
    enabled: engagementId !== undefined && itemId !== null,
    retry: false,
  });
}

export interface ComposerSave {
  engagementId: string;
  /** Null creates a new request. */
  itemId: string | null;
  /** The live create body for a new request. */
  create: { audit_area: string; description: string };
  patch: RequestItemPatchIn;
  /** A third party to delegate to, when the toggle is on. */
  delegateTo: string | null;
  send: boolean;
}

/** Save (create or patch), delegate, then send, refreshing every binder read after. */
export function useComposerSave() {
  const queryClient = useQueryClient();
  const create = useMutation({ ...createRequestItemMutation() });
  const update = useMutation({ ...updateRequestItemMutation() });
  const delegate = useMutation({ ...delegateRequestItemMutation() });
  const send = useMutation({ ...sendRequestItemMutation() });
  const run = async (input: ComposerSave): Promise<RequestItemV2Out> => {
    const engagement = { engagement_id: input.engagementId };
    const id =
      input.itemId ?? (await create.mutateAsync({ path: engagement, body: input.create })).id;
    const path = { ...engagement, item_id: id };
    let saved = await update.mutateAsync({ path, body: input.patch });
    if (input.delegateTo !== null) {
      await delegate.mutateAsync({ path, body: { contact_id: input.delegateTo } });
    }
    if (input.send) {
      saved = await send.mutateAsync({
        path,
        headers: { "Idempotency-Key": globalThis.crypto.randomUUID() },
      });
    }
    await queryClient.invalidateQueries();
    return saved;
  };
  const pending = create.isPending || update.isPending || delegate.isPending || send.isPending;
  return { run, pending };
}

/** SHL-14 d (P-06-T24): "Mark incorporated" on a close-intake request, `pending_incorporation` to
 * `incorporated` (`POST …/request-items/{id}/incorporate`, `request_item.update`). A person's act;
 * every binder read refreshes after, so the pill turns green from the server's row. */
export function useIncorporate() {
  const queryClient = useQueryClient();
  const incorporate = useMutation({ ...incorporateRequestItemMutation() });
  const run = async (engagementId: string, itemId: string): Promise<RequestItemV2Out> => {
    const saved = await incorporate.mutateAsync({
      path: { engagement_id: engagementId, item_id: itemId },
    });
    await queryClient.invalidateQueries();
    return saved;
  };
  return { run, pending: incorporate.isPending };
}
