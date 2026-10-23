// The portal home (P-08 §5.2, L3; docs/screens/POR-02.md): `GET /v1/portal/home` for the chosen
// scope and the welcome card's dismissal (`PUT /v1/portal/preferences`) over the generated client
// only. Every aggregate on the home is already filtered by the grant that covers its own scope
// (INV-4); the client draws it and never combines scopes.

import type { PortalHomeOut } from "@abacus/api-client";
import {
  getPortalHomeOptions,
  getPortalHomeQueryKey,
  updatePortalPreferencesMutation,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

function homeOptions(scopeId: string | null) {
  return getPortalHomeOptions(scopeId === null ? {} : { query: { scope_id: scopeId } });
}

export function usePortalHome(scopeId: string | null) {
  return useQuery({ ...homeOptions(scopeId), retry: false });
}

/** Dismiss the welcome card for this person and scope. The home carries no preference version
 * yet, so a scope never dismissed sends version 0 (docs/screens/POR-02.md, Open gaps). */
export function useDismissWelcome(scopeId: string | null) {
  const queryClient = useQueryClient();
  const key = getPortalHomeQueryKey(scopeId === null ? {} : { query: { scope_id: scopeId } });
  return useMutation({
    ...updatePortalPreferencesMutation(),
    onMutate: () => {
      queryClient.setQueryData<PortalHomeOut>(key, (home) =>
        home === undefined ? home : { ...home, welcome_dismissed: true },
      );
    },
  });
}
