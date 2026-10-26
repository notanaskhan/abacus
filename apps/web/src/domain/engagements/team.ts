// ENG-05's team (P-07-T39; DEC-327; docs/screens/ENG-05.md), over the generated client only: the
// roster with hours, the portal flag and independence, the team approval footer, the people
// "+ Add person" offers, and the EQR candidates with their SQMS 2 checks. Every write is a
// person's click; after one the roster, the approval and the record's tab count are read again.
// The server's refusals (`gate_unmet`, `eqr_on_team`, `eqr_not_eligible`, 403, 404) are the
// screen's to say.

import type { TeamRosterMemberOut } from "@abacus/api-client";
import {
  addTeamMemberMutation,
  assignEqrMutation,
  changeTeamRoleMutation,
  engagementRecordQueryKey,
  eqrCandidatesOptions,
  eqrCandidatesQueryKey,
  getTeamApprovalOptions,
  getTeamApprovalQueryKey,
  putPortalVisibilityMutation,
  removeTeamMemberMutation,
  sendRemindersMutation,
  teamCandidatesOptions,
  teamCandidatesQueryKey,
  teamOptions,
  teamQueryKey,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type TeamRole = TeamRosterMemberOut["role"];
/** The roles the team routes take (the EQR is set through `POST …/eqr`, DEC-327). */
export type TeamRouteRole = Exclude<TeamRole, "eqr_reviewer" | "client_service">;

const path = (engagementId: string) => ({ path: { engagement_id: engagementId } });

/** `GET …/team`: the roster (P-07-T30's hours, portal flag, proposal date and independence). */
export function useTeamRoster(engagementId: string) {
  return useQuery({ ...teamOptions(path(engagementId)), retry: false });
}

/** `GET …/team/approval`: the footer's "Team approved by … · changes since: …". */
export function useTeamApproval(engagementId: string) {
  return useQuery({ ...getTeamApprovalOptions(path(engagementId)), retry: false });
}

/** `GET …/team/candidates`: who "+ Add person" offers (active, unwalled staff not on the team). */
export function useTeamCandidates(engagementId: string, enabled: boolean) {
  return useQuery({ ...teamCandidatesOptions(path(engagementId)), retry: false, enabled });
}

/** `GET …/eqr/candidates`: eligibility per candidate; the current EQR is marked `current`. */
export function useEqrCandidates(engagementId: string, enabled = true) {
  return useQuery({ ...eqrCandidatesOptions(path(engagementId)), retry: false, enabled });
}

/** The team's writes; each reads the roster, the approval and the record again. */
export function useTeamWrites(engagementId: string) {
  const queryClient = useQueryClient();
  const refresh = async (): Promise<void> => {
    await Promise.all(
      [
        teamQueryKey(path(engagementId)),
        getTeamApprovalQueryKey(path(engagementId)),
        teamCandidatesQueryKey(path(engagementId)),
        eqrCandidatesQueryKey(path(engagementId)),
        engagementRecordQueryKey(path(engagementId)),
      ].map((queryKey) => queryClient.invalidateQueries({ queryKey })),
    );
  };
  const add = useMutation({ ...addTeamMemberMutation(), onSuccess: refresh });
  const change = useMutation({ ...changeTeamRoleMutation(), onSuccess: refresh });
  const remove = useMutation({ ...removeTeamMemberMutation(), onSuccess: refresh });
  const portal = useMutation({ ...putPortalVisibilityMutation(), onSuccess: refresh });
  const remind = useMutation({ ...sendRemindersMutation() });
  const eqr = useMutation({ ...assignEqrMutation(), onSuccess: refresh });
  const at = (userId: string) => ({ path: { engagement_id: engagementId, user_id: userId } });
  return {
    /** Adds the person; the server asks them to confirm independence (G2). */
    add: (userId: string, role: TeamRouteRole) =>
      add.mutateAsync({ ...path(engagementId), body: { user_id: userId, role } }),
    changeRole: (userId: string, role: TeamRouteRole) =>
      change.mutateAsync({ ...at(userId), body: { role } }),
    editHours: (userId: string, hours: string) =>
      change.mutateAsync({ ...at(userId), body: { budget_hours: hours } }),
    remove: (userId: string) => remove.mutateAsync(at(userId)),
    showOnPortal: (userId: string, shown: boolean) =>
      portal.mutateAsync({ ...at(userId), body: { shown_on_portal: shown } }),
    remind: (userIds: string[]) =>
      remind.mutateAsync({ ...path(engagementId), body: { user_ids: userIds } }),
    replaceEqr: (userId: string) =>
      eqr.mutateAsync({ ...path(engagementId), body: { user_id: userId } }),
    pending:
      add.isPending ||
      change.isPending ||
      remove.isPending ||
      portal.isPending ||
      remind.isPending ||
      eqr.isPending,
  };
}

/** Tenths of an hour from the server's decimal string ("37.0" → 370); null for none. */
export function tenthsOf(hours: string | null | undefined): number | null {
  if (hours == null || hours === "") return null;
  const m = /^(\d+)(?:\.(\d))?\d*$/.exec(hours.trim());
  if (m === null) return null;
  return Number(m[1]) * 10 + Number(m[2] ?? "0");
}

/** The hours column's total in tenths, or null when no row carries hours. */
export function hoursTotal(rows: readonly (string | null | undefined)[]): number | null {
  const tenths = rows.map(tenthsOf).filter((t): t is number => t !== null);
  return tenths.length === 0 ? null : tenths.reduce((a, b) => a + b, 0);
}

/** "172.0" from 1720 tenths: one decimal, as the handoff draws hours. */
export function hoursText(tenths: number): string {
  return `${String(Math.floor(tenths / 10))}.${String(tenths % 10)}`;
}
