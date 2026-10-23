// One binder (P-06 §5.2, L3): BND-02's reads and writes over the generated client only. The record,
// its rows, the 5-second live poll while the page is visible (DEC-23, DV-3), the client preview,
// the activity, a request's uploads and who sent it, and the row actions (visibility, waive,
// return to client, delete) plus the binder's publish, Undo and unpublish.

import type { BinderRequestRowOut, LiveItemOut, RequestStatus, WaiveIn } from "@abacus/api-client";
import {
  binderActivityOptions,
  binderClientPreviewOptions,
  binderLiveOptions,
  binderRequestsOptions,
  deleteRequestItemMutation,
  getBinderOptions,
  getEngagementOptions,
  listUploadsOptions,
  publishBinderMutation,
  requestItemActivityOptions,
  returnRequestItemToClientMutation,
  setClientVisibilityMutation,
  undoPublishBinderMutation,
  unpublishBinderMutation,
  waiveRequestItemMutation,
  workItemsOptions,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

/** The live poll's period (C5 §2: "Live poll (5 s)"). */
export const LIVE_POLL_MS = 5_000;

/** Whether the page is visible: the live poll runs only then (P-06-T12 acceptance). */
export function usePageVisible(): boolean {
  const read = (): boolean =>
    typeof document === "undefined" || document.visibilityState !== "hidden";
  const [visible, setVisible] = useState(read);
  useEffect(() => {
    const onChange = (): void => {
      setVisible(read());
    };
    document.addEventListener("visibilitychange", onChange);
    return () => {
      document.removeEventListener("visibilitychange", onChange);
    };
  }, []);
  return visible;
}

const path = (binderId: string) => ({ path: { binder_id: binderId } });

/** `GET /v1/binders/{id}`: the record, its categories with counts and `allowed_actions`. */
export function useBinder(binderId: string) {
  return useQuery({ ...getBinderOptions(path(binderId)), retry: false });
}

/** `GET /v1/binders/{id}/requests`: every row (BND-02 draws all categories at once). */
export function useBinderRequests(binderId: string) {
  return useQuery({ ...binderRequestsOptions(path(binderId)), retry: false });
}

/** `GET /v1/binders/{id}/live` every 5 s while the page is visible; nothing while it is hidden. */
export function useBinderLive(binderId: string, enabled: boolean) {
  const visible = usePageVisible();
  const on = enabled && visible;
  const query = useQuery({
    ...binderLiveOptions(path(binderId)),
    enabled: on,
    refetchInterval: on ? LIVE_POLL_MS : false,
    refetchIntervalInBackground: false,
    retry: false,
  });
  const byItem = new Map<string, LiveItemOut>(
    (query.data?.items ?? []).map((item) => [item.request_item_id, item]),
  );
  return { byItem, polling: on };
}

/** The client's view of the binder, for "Preview as client" and the dock's client wording. */
export function useClientPreview(binderId: string) {
  return useQuery({ ...binderClientPreviewOptions(path(binderId)), retry: false });
}

/** The Activity tab: binder and item events, identifiers only (the UI words them). */
export function useBinderActivity(binderId: string, enabled: boolean) {
  return useQuery({ ...binderActivityOptions(path(binderId)), enabled, retry: false });
}

/** The engagement and its work item, for "Jonah & Claire Feld · TY2025 Form 1040". */
export function useBinderContext(engagementId: string | undefined) {
  const engagement = useQuery({
    ...getEngagementOptions({ path: { engagement_id: engagementId ?? "" } }),
    enabled: engagementId !== undefined,
    retry: false,
  });
  const items = useQuery({
    ...workItemsOptions({ path: { engagement_id: engagementId ?? "" } }),
    enabled: engagementId !== undefined,
    retry: false,
  });
  return { engagement: engagement.data, workItems: items.data ?? [] };
}

/** A request's files and its activity (who sent it), for the dock. */
export function useRequestDetail(engagementId: string | undefined, itemId: string | null) {
  const enabled = engagementId !== undefined && itemId !== null;
  const p = { path: { engagement_id: engagementId ?? "", item_id: itemId ?? "" } };
  const uploads = useQuery({ ...listUploadsOptions(p), enabled, retry: false });
  const activity = useQuery({ ...requestItemActivityOptions(p), enabled, retry: false });
  return { uploads: uploads.data ?? [], activity: activity.data?.items ?? [] };
}

/** A fresh Idempotency-Key per client-visible effect (P-36). */
function idempotencyKey(): string {
  return globalThis.crypto.randomUUID();
}

function useRefreshBinder(binderId: string): () => void {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({
      predicate: (q) => {
        const key = q.queryKey[0] as { _id?: string; path?: { binder_id?: string } } | undefined;
        return key?.path?.binder_id === binderId || key?._id === "listBinders";
      },
    });
  };
}

/** The row ··· and Eye actions and the publish bar's, each refreshing the binder after. */
export function useBinderWrites(binderId: string, engagementId: string | undefined) {
  const refresh = useRefreshBinder(binderId);
  const visibility = useMutation({ ...setClientVisibilityMutation(), onSuccess: refresh });
  const waive = useMutation({ ...waiveRequestItemMutation(), onSuccess: refresh });
  const back = useMutation({ ...returnRequestItemToClientMutation(), onSuccess: refresh });
  const remove = useMutation({ ...deleteRequestItemMutation(), onSuccess: refresh });
  const publish = useMutation({ ...publishBinderMutation(), onSuccess: refresh });
  const undo = useMutation({ ...undoPublishBinderMutation(), onSuccess: refresh });
  const unpublish = useMutation({ ...unpublishBinderMutation(), onSuccess: refresh });
  const item = (itemId: string) => ({
    path: { engagement_id: engagementId ?? "", item_id: itemId },
  });
  return {
    setVisible: (itemId: string, visible: boolean) =>
      visibility.mutateAsync({ ...item(itemId), body: { client_visible: visible } }),
    waive: (itemId: string, body: WaiveIn) => waive.mutateAsync({ ...item(itemId), body }),
    returnToClient: (itemId: string, note: string) =>
      back.mutateAsync({
        ...item(itemId),
        body: { note },
        headers: { "Idempotency-Key": idempotencyKey() },
      }),
    remove: (itemId: string) => remove.mutateAsync(item(itemId)),
    publish: () =>
      publish.mutateAsync({ ...path(binderId), headers: { "Idempotency-Key": idempotencyKey() } }),
    undoPublish: () => undo.mutateAsync(path(binderId)),
    unpublish: (reason: string) => unpublish.mutateAsync({ ...path(binderId), body: { reason } }),
  };
}

/** A request counts towards "n of m satisfied": received, or waived as not applicable. */
export function isSatisfied(row: Pick<BinderRequestRowOut, "status">): boolean {
  const done: readonly RequestStatus[] = ["received", "not_applicable"];
  return done.includes(row.status);
}

/** Whether the server lets this person take `action` on the record or row. */
export function allows(
  record: { allowed_actions?: string[] } | undefined,
  action: string,
): boolean {
  return (record?.allowed_actions ?? []).includes(action);
}
