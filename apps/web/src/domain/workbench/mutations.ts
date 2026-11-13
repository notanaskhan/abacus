// Workbench sessions' writes (W-02 §4.3): blank create, rename, soft delete, context attach and
// remove, and the drill. Each is the session owner's on the server (`session.manage`); the screen
// shows a control only when the snapshot's `allowed_actions` holds `manage` (AC-L5). Every write
// sends an Idempotency-Key; rename sends `If-Match` with the row's version.

import type { ContextRefIn } from "@abacus/api-client";
import {
  attachContextMutation,
  createSessionMutation,
  deleteSessionMutation,
  listSessionsQueryKey,
  postSessionMessageMutation,
  removeContextMutation,
  renameSessionMutation,
  sessionDrillMutation,
} from "@abacus/api-client/query";
import { useMutation, useQueryClient } from "@tanstack/react-query";

const key = (): string => crypto.randomUUID();

function useInvalidateList() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: [listSessionsQueryKey()[0]] });
}

/** `POST /v1/workbench/sessions` with no subject: a blank, firm-wide session (WB-02 a). */
export function useCreateSession() {
  const invalidate = useInvalidateList();
  const m = useMutation({ ...createSessionMutation(), onSuccess: invalidate });
  return { ...m, create: () => m.mutateAsync({ body: {} }) };
}

export function useRenameSession() {
  const invalidate = useInvalidateList();
  const m = useMutation({ ...renameSessionMutation(), onSuccess: invalidate });
  return {
    ...m,
    rename: (sessionId: string, title: string, version: string) =>
      m.mutateAsync({
        path: { session_id: sessionId },
        body: { title },
        headers: { "If-Match": version },
      }),
  };
}

/** Soft delete: "Delete this session? Its run trace stays in the firm audit log." (AC-L4). */
export function useDeleteSession() {
  const invalidate = useInvalidateList();
  const m = useMutation({ ...deleteSessionMutation(), onSuccess: invalidate });
  return {
    ...m,
    remove: (sessionId: string) =>
      m.mutateAsync({ path: { session_id: sessionId }, headers: { "Idempotency-Key": key() } }),
  };
}

export function useAttachContext() {
  const m = useMutation(attachContextMutation());
  return {
    ...m,
    attach: (sessionId: string, items: ContextRefIn[]) =>
      m.mutateAsync({
        path: { session_id: sessionId },
        body: { items },
        headers: { "Idempotency-Key": key() },
      }),
  };
}

export function useRemoveContext() {
  const m = useMutation(removeContextMutation());
  return {
    ...m,
    detach: (sessionId: string, itemId: string) =>
      m.mutateAsync({
        path: { session_id: sessionId, item_id: itemId },
        headers: { "Idempotency-Key": key() },
      }),
  };
}

/** WB-03 d: a result row's records, code-rendered into the thread with no model call (AC-R4). */
export function useSessionDrill() {
  const m = useMutation(sessionDrillMutation());
  return {
    ...m,
    drill: (sessionId: string, artifactId: string, groupKey: string) =>
      m.mutateAsync({
        path: { session_id: sessionId },
        body: { artifact_id: artifactId, group_key: groupKey },
        headers: { "Idempotency-Key": key() },
      }),
  };
}

/** W-02-T16: the person's message (WB-02 e); its turn runs in the session's workflow. */
export function usePostMessage() {
  const m = useMutation(postSessionMessageMutation());
  return {
    ...m,
    post: (sessionId: string, body: string) =>
      m.mutateAsync({
        path: { session_id: sessionId },
        body: { body },
        headers: { "Idempotency-Key": key() },
      }),
  };
}
