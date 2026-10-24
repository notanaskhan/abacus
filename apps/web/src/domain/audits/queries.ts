// The audits domain's reads (A-01-T06; docs/contracts/audits-cockpit.md), over the generated client
// only. In fixture mode the same calls answer from `fixtures/handlers/audits.ts`.

import { auditCockpitOptions, auditSourceDocumentsOptions } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";

/** `GET /v1/audits/{id}/cockpit`: the audit bar, overview, registered rail rows and dock tabs. */
export function useAuditCockpit(workItemId: string) {
  return useQuery(auditCockpitOptions({ path: { work_item_id: workItemId } }));
}

/** `GET /v1/audits/{id}/source-documents`: the requests across the work item's PBC binders. */
export function useSourceDocuments(
  workItemId: string,
  sort: "missing_first" | "received_first" = "missing_first",
) {
  return useQuery(
    auditSourceDocumentsOptions({ path: { work_item_id: workItemId }, query: { sort } }),
  );
}
