// CLI-08's reads and writes (P-07-T48; docs/contracts/acceptance-independence.md, live since
// P-07-T41), over the generated client only. Every write is a person's own act: the server
// refuses anyone confirming for someone else, the agent, the system and a stale second factor.

import type {
  ConcludeIn,
  IndependenceSummaryOut,
  MemberConfirmationOut,
} from "@abacus/api-client";
import {
  concludeIndependenceMutation,
  confirmIndependenceMutation,
  declineIndependenceMutation,
  getConflictCheckOptions,
  getIndependenceOptions,
  getNasOptions,
  getRotationOptions,
  sendRemindersMutation,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export function useIndependence(engagementId: string) {
  return useQuery(getIndependenceOptions({ path: { engagement_id: engagementId } }));
}

export function useNas(engagementId: string, enabled: boolean) {
  return useQuery({ ...getNasOptions({ path: { engagement_id: engagementId } }), enabled });
}

export function useRotation(engagementId: string, enabled: boolean) {
  return useQuery({ ...getRotationOptions({ path: { engagement_id: engagementId } }), enabled });
}

/** The conflict check CLI-08 c reads, when the route names one (`?check=`). */
export function useConflictCheck(checkId: string | null, enabled: boolean) {
  return useQuery({
    ...getConflictCheckOptions({ path: { check_id: checkId ?? "" } }),
    enabled: enabled && checkId !== null,
  });
}

export function useIndependenceWrites(engagementId: string) {
  const queryClient = useQueryClient();
  const refresh = (): void => {
    void queryClient.invalidateQueries({
      predicate: (q) => {
        const id = (q.queryKey[0] as { _id?: string } | undefined)?._id ?? "";
        return id === "getIndependence" || id === "getNas";
      },
    });
  };
  const path = { engagement_id: engagementId };
  const confirm = useMutation({ ...confirmIndependenceMutation(), onSuccess: refresh });
  const decline = useMutation({ ...declineIndependenceMutation(), onSuccess: refresh });
  const remind = useMutation({ ...sendRemindersMutation(), onSuccess: refresh });
  const conclude = useMutation({ ...concludeIndependenceMutation(), onSuccess: refresh });
  return {
    confirm: (statementVersion: string, codes: readonly string[]) =>
      confirm.mutateAsync({
        path,
        body: { statement_version: statementVersion, statement_codes: [...codes] },
      }),
    decline: (note: string) => decline.mutateAsync({ path, body: { note } }),
    remind: (userIds: readonly string[]) =>
      remind.mutateAsync({ path, body: { user_ids: [...userIds] } }),
    conclude: (body: ConcludeIn) => conclude.mutateAsync({ path, body }),
    busy: confirm.isPending || decline.isPending || remind.isPending || conclude.isPending,
  };
}

/** The members still to confirm (requested), and those who declined. */
export function pendingMembers(summary: IndependenceSummaryOut): MemberConfirmationOut[] {
  return (summary.members ?? []).filter((m) => m.confirmation === "requested");
}

export function declinedMembers(summary: IndependenceSummaryOut): MemberConfirmationOut[] {
  return (summary.members ?? []).filter((m) => m.confirmation === "declined");
}

/** The viewer may conclude: the server says so (`independence.conclude`, the engagement partner,
 * every precondition met). Nobody else ever gets an enabled Conclude. */
export function mayConclude(summary: IndependenceSummaryOut): boolean {
  return (summary.allowed_actions ?? []).includes("independence.conclude");
}
