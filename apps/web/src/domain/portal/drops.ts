// A drop's sort, from the client's side (R-01-T10; docs/screens/POR-03.md, API): after files are
// dropped anywhere on the binder, `GET /v1/portal/drops/{batch_id}` is polled until the batch is
// settled (every file has an outcome). A `rule_linked` file sits on its request ("Suggested — …
// will confirm", DEC-58 a); a `waiting` or `duplicate_flagged` file goes to the firm to sort (a
// duplicate reads as waiting to the client, DEC-323); a `refused` file names its refusal. Generated
// client only.

import type { DropBatchOut, DropFileOut } from "@abacus/api-client";
import { getDropBatchOptions } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";

/** How often an unsettled batch is read again. */
export const DROP_POLL_MS = 1000;

export function useDropBatch(batchId: string | undefined) {
  return useQuery({
    ...getDropBatchOptions({ path: { batch_id: batchId ?? "" } }),
    enabled: batchId !== undefined,
    retry: false,
    refetchInterval: (query) => (query.state.data?.settled === true ? false : DROP_POLL_MS),
  });
}

export interface DropOutcome {
  /** Files that landed on a request, pending a person's accept. */
  matched: readonly DropFileOut[];
  /** Files the firm sorts by hand ("Brightwater Hale will sort this"). */
  unsorted: readonly DropFileOut[];
  /** Files the upload policy refused, with the refusal code. */
  refused: readonly DropFileOut[];
}

/** A settled batch's files by what happened to them; null while the sort is still running. */
export function dropOutcome(batch: DropBatchOut | undefined): DropOutcome | null {
  if (batch?.settled !== true) return null;
  const files = batch.files;
  return {
    matched: files.filter((f) => f.outcome === "rule_linked"),
    unsorted: files.filter((f) => f.outcome === "waiting" || f.outcome === "duplicate_flagged"),
    refused: files.filter((f) => f.outcome === "refused"),
  };
}
