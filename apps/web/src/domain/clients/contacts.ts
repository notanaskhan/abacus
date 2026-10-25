// Contacts and portal access (P-07-T33; docs/contracts/contacts-access.md): CLI-04's reads and
// writes over the generated client only. The list carries the header counts and the
// delegated-requests footer for the client's whole list (DEC-302); a walled or unknown client
// answers 404 (INV-3). Every write is a person's act: the agent never invites, resends, revokes,
// changes scope or unlocks (INV-1). An invitation and a revoke need fresh MFA (the server says so).

import type { ContactRoleOut, ContactRowOut, GrantIn, RequestItemOut } from "@abacus/api-client";
import {
  changeContactAccessMutation,
  getContactOptions,
  getContactQueryKey,
  inviteContactMutation,
  listContactsOptions,
  listContactsQueryKey,
  listRequestItemsOptions,
  resendInvitationMutation,
  revokeInvitationMutation,
  unlockContactMutation,
} from "@abacus/api-client/query";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

export type ContactRoleCode = ContactRoleOut["role"];
export type GrantRole = GrantIn["role"];

/** The contact roles a third party holds: such a contact sees only its delegated requests. */
const THIRD_PARTY_ROLES: ReadonlySet<ContactRoleCode> = new Set([
  "recordkeeper",
  "tpa",
  "custodian",
  "payroll_provider",
]);

/** A third party (CLI-04 acceptance: "third parties are scoped to delegated requests"). */
export function isThirdParty(row: ContactRowOut): boolean {
  return (row.roles ?? []).some((r) => THIRD_PARTY_ROLES.has(r.role));
}

/** The grant role a client-wide invitation gives a contact of this role (ADR-146 grant roles). */
const GRANT_ROLE: Readonly<Record<ContactRoleCode, GrantRole>> = {
  owner: "owner",
  cfo: "owner",
  controller: "owner",
  trustee: "trustee",
  executor: "trustee",
  taxpayer: "taxpayer",
  spouse: "spouse",
  plan_sponsor_officer: "plan_administrator",
  recordkeeper: "third_party",
  tpa: "third_party",
  custodian: "third_party",
  payroll_provider: "third_party",
  other: "contributor",
};

/** The O3 sheet's grant set: a third party gets exactly the ticked requests; anyone else the
 * client, in the grant role their contact role maps to. */
export function grantsFor(
  row: ContactRowOut,
  clientId: string,
  requestItemIds: readonly string[],
): GrantIn[] {
  if (isThirdParty(row)) {
    const first = requestItemIds[0];
    return first === undefined
      ? []
      : [
          {
            role: "third_party",
            scope_kind: "request_item",
            scope_id: first,
            request_item_ids: [...requestItemIds],
          },
        ];
  }
  const role = (row.roles ?? [])[0]?.role;
  return [
    {
      role: role === undefined ? "contributor" : GRANT_ROLE[role],
      scope_kind: "client",
      scope_id: clientId,
    },
  ];
}

/** `GET /v1/clients/{id}/contacts`: rows, `summary` (the header) and `delegated` (the footer). */
export function useContacts(clientId: string, enabled = true) {
  return useQuery({
    ...listContactsOptions({ path: { client_id: clientId }, query: { limit: 200 } }),
    retry: false,
    enabled,
  });
}

/** `GET /v1/contacts/{id}`: the O2 drawer and the O3 sheet's ticks and version. */
export function useContact(contactId: string | null) {
  return useQuery({
    ...getContactOptions({ path: { contact_id: contactId ?? "" } }),
    retry: false,
    enabled: contactId !== null,
  });
}

/** The request items of the client's active engagements: the titles the sheet and the drawer
 * name for a contact's delegated requests (C5's list per engagement). */
export function useClientRequestItems(
  engagementIds: readonly string[],
  enabled = true,
): ReadonlyMap<string, RequestItemOut> {
  const results = useQueries({
    queries: engagementIds.map((id) => ({
      ...listRequestItemsOptions({ path: { engagement_id: id } }),
      retry: false,
      enabled,
    })),
  });
  const out = new Map<string, RequestItemOut>();
  for (const r of results) for (const item of r.data ?? []) out.set(item.id, item);
  return out;
}

/** CLI-04's writes; each reads the list (and the drawer) again on success. */
export function useContactWrites(clientId: string) {
  const queryClient = useQueryClient();
  const again = async (contactId?: string): Promise<void> => {
    await queryClient.invalidateQueries({
      queryKey: listContactsQueryKey({ path: { client_id: clientId } }),
    });
    if (contactId !== undefined) {
      await queryClient.invalidateQueries({
        queryKey: getContactQueryKey({ path: { contact_id: contactId } }),
      });
    }
  };
  const invite = useMutation({ ...inviteContactMutation() });
  const resend = useMutation({ ...resendInvitationMutation() });
  const revoke = useMutation({ ...revokeInvitationMutation() });
  const access = useMutation({ ...changeContactAccessMutation() });
  const unlock = useMutation({ ...unlockContactMutation() });
  return {
    invite: async (contactId: string, grants: GrantIn[]) => {
      const out = await invite.mutateAsync({
        path: { contact_id: contactId },
        body: { grants, expires_in_days: 14 },
        headers: { "Idempotency-Key": globalThis.crypto.randomUUID() },
      });
      await again(contactId);
      return out;
    },
    resend: async (contactId: string, invitationId: string) => {
      const out = await resend.mutateAsync({ path: { invitation_id: invitationId } });
      await again(contactId);
      return out;
    },
    revoke: async (contactId: string, invitationId: string) => {
      const out = await revoke.mutateAsync({ path: { invitation_id: invitationId } });
      await again(contactId);
      return out;
    },
    changeScope: async (contactId: string, seenVersion: number, grants: GrantIn[]) => {
      const out = await access.mutateAsync({
        path: { contact_id: contactId },
        body: { seen_version: seenVersion, grants },
      });
      await again(contactId);
      return out;
    },
    unlock: async (contactId: string) => {
      const out = await unlock.mutateAsync({ path: { contact_id: contactId } });
      await again(contactId);
      return out;
    },
    pending:
      invite.isPending ||
      resend.isPending ||
      revoke.isPending ||
      access.isPending ||
      unlock.isPending,
  };
}
