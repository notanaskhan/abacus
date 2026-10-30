// C3 checkpoints (P-04-T32; SHL-16, P-04-T43): the history of a record's checkpoints, one
// checkpoint's detail (steps, field diff, totals) against the current or the previous one, and the
// person's writes. Every write carries the content hash the person saw (`seen_hash`), waits for the
// server (never optimistic) and refreshes the history and the detail. Restore never rewrites the
// past: the server answers a new checkpoint that copies the old one.
import type { CheckpointItemOut } from "@abacus/api-client";
import {
  checkpointApproveMutation,
  checkpointHistoryOptions,
  checkpointOptions,
  checkpointRejectMutation,
  checkpointRenameMutation,
  checkpointRestoreMutation,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type CheckpointFilter = "agent" | "named" | "all";

export interface CheckpointTarget {
  type: string;
  id: string;
}

export function useCheckpointHistory(target: CheckpointTarget, filter: CheckpointFilter) {
  return useQuery(
    checkpointHistoryOptions({
      query: { target_type: target.type, target_id: target.id, filter },
    }),
  );
}

export function useCheckpoint(id: string | null, compare: "current" | "previous") {
  return useQuery({
    ...checkpointOptions({ path: { checkpoint_id: id ?? "" }, query: { compare } }),
    enabled: id !== null,
  });
}

export interface CheckpointWrites {
  approve: (cp: CheckpointItemOut) => Promise<CheckpointItemOut>;
  reject: (cp: CheckpointItemOut, reason: string) => Promise<CheckpointItemOut>;
  rename: (
    cp: CheckpointItemOut,
    patch: { name?: string | null; starred?: boolean },
  ) => Promise<CheckpointItemOut>;
  restore: (cp: CheckpointItemOut) => Promise<CheckpointItemOut>;
}

export function useCheckpointWrites(): CheckpointWrites {
  const client = useQueryClient();
  const refresh = (): void => {
    void Promise.all(
      ["checkpointHistory", "checkpoint"].map((id) =>
        client.invalidateQueries({ queryKey: [{ _id: id }] }),
      ),
    );
  };
  // P-04-T47: a decision moves the record's own state too (the sync chip goes "Out of sync" once
  // an import or a checkpoint is approved), so every read whose key names the record refetches.
  // The review domain imports no record module: it matches the record's id in the query key.
  const decided = (cp: CheckpointItemOut): void => {
    refresh();
    void client.invalidateQueries({
      predicate: (query) => JSON.stringify(query.queryKey).includes(cp.target_id),
    });
  };
  const approve = useMutation({
    ...checkpointApproveMutation(),
    onSuccess: (cp) => {
      decided(cp);
    },
  });
  const reject = useMutation({
    ...checkpointRejectMutation(),
    onSuccess: (cp) => {
      decided(cp);
    },
  });
  const rename = useMutation({ ...checkpointRenameMutation(), onSuccess: refresh });
  const restore = useMutation({ ...checkpointRestoreMutation(), onSuccess: refresh });
  const at = (cp: CheckpointItemOut) => ({ path: { checkpoint_id: cp.id } });
  return {
    approve: (cp) => approve.mutateAsync({ ...at(cp), body: { seen_hash: cp.content_hash } }),
    reject: (cp, reason) =>
      reject.mutateAsync({ ...at(cp), body: { seen_hash: cp.content_hash, reason } }),
    rename: (cp, patch) =>
      rename.mutateAsync({
        ...at(cp),
        body: {
          ...(patch.name === undefined ? {} : { name: patch.name }),
          ...(patch.starred === undefined ? {} : { starred: patch.starred }),
        },
      }),
    restore: (cp) => restore.mutateAsync({ ...at(cp), body: { seen_hash: cp.content_hash } }),
  };
}
