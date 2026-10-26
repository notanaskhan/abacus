// Delegation to a third party (P-06-T10; C5 "Delegate to a third party"): a person gives one
// client contact a grant on one request (`POST …/request-items/{id}/delegate {contact_id}`,
// `request_item.delegate`: partner, manager, senior; never an agent). The contact then answers it
// in the third-party room (POR-14, R-01 #418). AUD-03 e's "Request from third party…" uses it.

import { delegateRequestItemMutation } from "@abacus/api-client/query";
import { useMutation, useQueryClient } from "@tanstack/react-query";

export function useDelegate() {
  const queryClient = useQueryClient();
  const delegate = useMutation({
    ...delegateRequestItemMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        predicate: (q) => {
          const id = (q.queryKey[0] as { _id?: string } | undefined)?._id ?? "";
          return id === "auditSourceDocuments" || id === "binderRequests";
        },
      });
    },
  });
  return {
    delegate: (engagementId: string, itemId: string, contactId: string) =>
      delegate.mutateAsync({
        path: { engagement_id: engagementId, item_id: itemId },
        body: { contact_id: contactId },
      }),
    delegating: delegate.isPending,
  };
}
