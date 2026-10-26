// The audits domain's reads (A-01-T06; docs/contracts/audits-cockpit.md), over the generated client
// only. In fixture mode the same calls answer from `fixtures/handlers/audits.ts`.

import {
  acceptMutation,
  auditCockpitOptions,
  auditSourceDocumentsOptions,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

/** `GET /v1/audits/{id}/cockpit`: the audit bar, overview, registered rail rows and dock tabs. */
export function useAuditCockpit(workItemId: string) {
  return useQuery(auditCockpitOptions({ path: { work_item_id: workItemId } }));
}

/** `GET /v1/audits/{id}/source-documents`: the requests across the work item's PBC binders. */
export function useSourceDocuments(
  workItemId: string,
  sort: "missing_first" | "received_first" = "missing_first",
  options: { poll?: number } = {},
) {
  return useQuery({
    ...auditSourceDocumentsOptions({ path: { work_item_id: workItemId }, query: { sort } }),
    // AUD-03 rows follow P-06's binder poll (P-15: polling first, no SSE before P-10).
    ...(options.poll === undefined ? {} : { refetchInterval: options.poll }),
  });
}

/** A person's Accept on an uploaded file (`evidence.accept`, human only; DEC-37). The Source
 * Documents aggregate, the cockpit rail and the screening card read again afterwards. */
export function useSourceDocumentDecisions() {
  const queryClient = useQueryClient();
  const refresh = (): void => {
    void queryClient.invalidateQueries({
      predicate: (q) => {
        const id = (q.queryKey[0] as { _id?: string } | undefined)?._id ?? "";
        return id === "auditSourceDocuments" || id === "auditCockpit" || id === "screeningCard";
      },
    });
  };
  const accept = useMutation({ ...acceptMutation(), onSettled: refresh });
  return {
    accept: (engagementId: string, versionId: string) =>
      accept.mutateAsync({
        path: { engagement_id: engagementId, version_id: versionId },
        body: {},
      }),
    accepting: accept.isPending,
    refresh,
  };
}

/** A 404 from the audits routes: outside the tenant, behind a wall, or not assurance (INV-3). */
export function isNotFound(error: unknown): boolean {
  if (typeof error !== "object" || error === null) return false;
  const detail = (error as { detail?: unknown }).detail;
  return detail === "not_found" || (error as { status?: unknown }).status === 404;
}
