import type { StaffMemberOut } from "@abacus/api-client";
import {
  changeFirmRoleMutation,
  inviteStaffMutation,
  meOptions,
  resendStaffInvitationMutation,
  revokeStaffInvitationMutation,
  revokeStaffMutation,
  staffOptions,
  staffQueryKey,
} from "@abacus/api-client/query";
import {
  Alert,
  Button,
  Dialog,
  Input,
  Label,
  Panel,
  Skeleton,
  StatusPill,
  Table,
  Td,
  Th,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type SyntheticEvent, useEffect, useState } from "react";
import { errorMessage } from "../api";
import { ConfirmItsYou, isForbidden } from "../shell/mfa";

type Role = "firm_admin" | "practice_leader" | "quality_partner";
const ROLES: [Role | "", string][] = [
  ["", "Team member"],
  ["firm_admin", "Firm administrator"],
  ["practice_leader", "Practice leader"],
  ["quality_partner", "Quality partner"],
];
const SELECT = "h-8 rounded-[var(--radius-control)] border border-line bg-surface px-2 text-sm";

function roleLabel(role: string | null | undefined): string {
  return ROLES.find(([value]) => value === (role ?? ""))?.[1] ?? "Team member";
}

function refusal(error: unknown): string {
  const code = errorMessage(error);
  if (code === "last_admin") return "The firm needs at least one firm administrator.";
  return code;
}

/** SPEC-024 AC-3, AC-4: the firm's people, their roles, and invitations. */
export function FirmPeople(): JSX.Element {
  const queryClient = useQueryClient();
  const list = useQuery({ ...staffOptions(), retry: false });
  const me = useQuery(meOptions());
  const [confirm, setConfirm] = useState(false);
  const [revoking, setRevoking] = useState<StaffMemberOut | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const forbidden = list.isError && isForbidden(list.error);
  useEffect(() => {
    if (forbidden) setConfirm(true);
  }, [forbidden]);
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: staffQueryKey() });
  };
  const handlers = {
    onSuccess: () => {
      setFailure(null);
      refresh();
    },
    onError: (error: unknown) => {
      if (isForbidden(error)) setConfirm(true);
      else setFailure(refusal(error));
      refresh();
    },
  };
  const role = useMutation({ ...changeFirmRoleMutation(), ...handlers });
  const revoke = useMutation({
    ...revokeStaffMutation(),
    ...handlers,
    onSettled: () => {
      setRevoking(null);
    },
  });
  const resend = useMutation({ ...resendStaffInvitationMutation(), ...handlers });
  const cancel = useMutation({ ...revokeStaffInvitationMutation(), ...handlers });

  return (
    <div className="flex flex-col gap-4">
      {list.isPending ? (
        <Skeleton className="h-32" />
      ) : list.isError ? (
        forbidden ? (
          <Alert
            title="Confirm it's you"
            action={
              <Button
                size="sm"
                onClick={() => {
                  setConfirm(true);
                }}
              >
                Sign in again
              </Button>
            }
          >
            Managing people needs a recent sign-in. If it still isn&apos;t allowed, only firm
            administrators can manage people.
          </Alert>
        ) : (
          <Alert title="Couldn't load your people">{errorMessage(list.error)}</Alert>
        )
      ) : (
        <>
          <InvitePanel onDone={refresh} onForbidden={setConfirm} />
          {failure !== null && (
            <p role="alert" className="text-sm text-danger">
              {failure}
            </p>
          )}
          <Panel title="People">
            <div className="overflow-x-auto">
              <Table className="min-w-[640px]">
                <thead>
                  <tr>
                    <Th>Name</Th>
                    <Th>Email</Th>
                    <Th>Role</Th>
                    <Th>Status</Th>
                    <Th>
                      <span className="sr-only">Actions</span>
                    </Th>
                  </tr>
                </thead>
                <tbody>
                  {list.data.members.map((m) => (
                    <tr key={m.user_id}>
                      <Td>
                        {m.display_name}
                        {m.user_id === me.data?.user_id && (
                          <span className="text-muted"> (you)</span>
                        )}
                      </Td>
                      <Td className="text-muted">{m.email}</Td>
                      <Td>
                        {m.status === "active" ? (
                          <select
                            aria-label={`Role for ${m.display_name}`}
                            className={SELECT}
                            value={m.firm_role ?? ""}
                            disabled={role.isPending}
                            onChange={(event) => {
                              const next = event.target.value;
                              role.mutate({
                                path: { user_id: m.user_id },
                                body: { firm_role: next === "" ? null : (next as Role) },
                              });
                            }}
                          >
                            {ROLES.map(([value, label]) => (
                              <option key={value} value={value}>
                                {label}
                              </option>
                            ))}
                          </select>
                        ) : (
                          roleLabel(m.firm_role)
                        )}
                      </Td>
                      <Td>
                        {m.status === "active" ? (
                          <StatusPill tone="success">Active</StatusPill>
                        ) : (
                          <StatusPill tone="neutral">Access removed</StatusPill>
                        )}
                      </Td>
                      <Td>
                        {m.status === "active" && m.user_id !== me.data?.user_id && (
                          <Button
                            size="sm"
                            variant="danger"
                            onClick={() => {
                              setRevoking(m);
                            }}
                          >
                            Remove access
                          </Button>
                        )}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          </Panel>
          <Panel title="Pending invitations">
            {list.data.invitations.length === 0 ? (
              <p className="text-sm text-muted">No pending invitations.</p>
            ) : (
              <ul className="flex flex-col divide-y divide-line text-sm">
                {list.data.invitations.map((i) => (
                  <li
                    key={i.id}
                    className="flex flex-wrap items-center justify-between gap-2 py-2"
                  >
                    <span>
                      {i.email} · {roleLabel(i.firm_role)}
                      <span className="block text-xs text-muted">
                        Expires {new Date(i.expires_at).toLocaleDateString()}
                      </span>
                    </span>
                    <span className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          resend.mutate({ path: { invitation_id: i.id } });
                        }}
                      >
                        Resend
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          cancel.mutate({ path: { invitation_id: i.id } });
                        }}
                      >
                        Revoke
                      </Button>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </>
      )}
      <Dialog
        open={revoking !== null}
        onOpenChange={(open) => {
          if (!open) setRevoking(null);
        }}
        title={`Remove ${revoking?.display_name ?? ""}'s access?`}
        description="They can't open anything in your firm from their next click. Their past work stays."
      >
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={() => {
              setRevoking(null);
            }}
          >
            Cancel
          </Button>
          <Button
            variant="danger"
            disabled={revoke.isPending}
            onClick={() => {
              if (revoking !== null) revoke.mutate({ path: { user_id: revoking.user_id } });
            }}
          >
            Remove access
          </Button>
        </div>
      </Dialog>
      <ConfirmItsYou open={confirm} onOpenChange={setConfirm} />
    </div>
  );
}

function InvitePanel({
  onDone,
  onForbidden,
}: {
  onDone: () => void;
  onForbidden: (open: boolean) => void;
}): JSX.Element {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role | "">("");
  const invite = useMutation({
    ...inviteStaffMutation(),
    onSuccess: () => {
      setEmail("");
      setRole("");
      onDone();
    },
    onError: (error) => {
      if (isForbidden(error)) onForbidden(true);
    },
  });
  const submit = (event: SyntheticEvent): void => {
    event.preventDefault();
    invite.mutate({ body: { email: email.trim(), firm_role: role === "" ? null : role } });
  };
  return (
    <Panel title="Invite someone">
      <form className="flex flex-wrap items-end gap-3" onSubmit={submit}>
        <div className="flex flex-col gap-1">
          <Label htmlFor="invite-email">Email</Label>
          <Input
            id="invite-email"
            type="email"
            required
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
            }}
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="invite-role">Role</Label>
          <select
            id="invite-role"
            className={SELECT}
            value={role}
            onChange={(event) => {
              setRole(event.target.value as Role | "");
            }}
          >
            {ROLES.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <Button type="submit" disabled={invite.isPending || email.trim() === ""}>
          Send invitation
        </Button>
      </form>
      {invite.isSuccess && <p className="text-sm text-ok">Invitation sent.</p>}
      {invite.isError && !isForbidden(invite.error) && (
        <p role="alert" className="text-sm text-danger">
          {errorMessage(invite.error)}
        </p>
      )}
    </Panel>
  );
}
