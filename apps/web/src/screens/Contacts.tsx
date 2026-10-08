import type { ClientContactOut } from "@abacus/api-client";
import {
  clientContactsOptions,
  clientContactsQueryKey,
  inviteClientMutation,
  removeClientContactMutation,
  resendClientInvitationMutation,
  revokeClientInvitationMutation,
} from "@abacus/api-client/query";
import {
  Alert,
  Button,
  Dialog,
  EmptyState,
  Input,
  Label,
  Skeleton,
  StatusPill,
  Table,
  Td,
  Th,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type SyntheticEvent, useState } from "react";
import { errorMessage } from "../api";

const ROLE: Record<string, string> = {
  client_admin: "Client admin",
  client_contributor: "Contributor",
};

type Pending = { kind: "revoke" | "resend" | "remove"; contact: ClientContactOut } | null;

/** SPEC-016 AC-5: client members and pending invitations; the link is never shown. */
export function Contacts({ engagementId }: { engagementId: string }): JSX.Element {
  const queryClient = useQueryClient();
  const path = { engagement_id: engagementId };
  const contacts = useQuery(clientContactsOptions({ path }));
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: clientContactsQueryKey({ path }) });
  };
  const [inviting, setInviting] = useState(false);
  const [pending, setPending] = useState<Pending>(null);
  const revoke = useMutation({ ...revokeClientInvitationMutation(), onSuccess: refresh });
  const resend = useMutation({ ...resendClientInvitationMutation(), onSuccess: refresh });
  const remove = useMutation({ ...removeClientContactMutation(), onSuccess: refresh });
  const failed = revoke.error ?? resend.error ?? remove.error;

  const confirm = (): void => {
    if (pending === null) return;
    const id = pending.contact.id;
    if (pending.kind === "revoke") revoke.mutate({ path: { ...path, invitation_id: id } });
    if (pending.kind === "resend") resend.mutate({ path: { ...path, invitation_id: id } });
    if (pending.kind === "remove") remove.mutate({ path: { ...path, user_id: id } });
    setPending(null);
  };

  const inviteButton = (
    <Button
      onClick={() => {
        setInviting(true);
      }}
    >
      Invite client contact
    </Button>
  );

  return (
    <section aria-labelledby="contacts-heading" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="contacts-heading" className="text-2xl">
            Client contacts
          </h2>
          <p className="text-sm text-muted">
            People at the client who can see what you share and send evidence. Invitations are
            emailed; links work once and expire after 7 days.
          </p>
        </div>
        {inviteButton}
      </div>
      {failed !== null && <Alert title="That didn't work">{errorMessage(failed)}</Alert>}
      {contacts.isPending ? (
        <Skeleton className="h-40" />
      ) : contacts.isError ? (
        <Alert
          title="Couldn't load contacts"
          action={
            <Button size="sm" variant="outline" onClick={() => void contacts.refetch()}>
              Retry
            </Button>
          }
        >
          {errorMessage(contacts.error)}
        </Alert>
      ) : contacts.data.length === 0 ? (
        <EmptyState title="No client contacts yet" action={inviteButton}>
          Invite the client&apos;s finance lead as a client admin; they can invite colleagues.
        </EmptyState>
      ) : (
        <div className="overflow-x-auto rounded-[var(--radius-panel)] border border-line bg-surface">
          <Table className="min-w-[640px]">
            <thead>
              <tr>
                <Th>Contact</Th>
                <Th>Role</Th>
                <Th>Status</Th>
                <Th>
                  <span className="sr-only">Actions</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {contacts.data.map((c) => (
                <tr key={`${c.kind}-${c.id}`}>
                  <Td className="font-semibold">{c.email ?? "Client member"}</Td>
                  <Td>{ROLE[c.role] ?? c.role}</Td>
                  <Td>
                    {c.kind === "member" ? (
                      <StatusPill tone="success">Joined</StatusPill>
                    ) : (
                      <span className="inline-flex items-center gap-2">
                        <StatusPill tone="info">Invited</StatusPill>
                        {c.expires_at !== null && (
                          <span className="text-xs text-muted">
                            until {new Date(c.expires_at).toLocaleDateString()}
                          </span>
                        )}
                      </span>
                    )}
                  </Td>
                  <Td className="text-right whitespace-nowrap">
                    {c.kind === "invitation" ? (
                      <>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setPending({ kind: "resend", contact: c });
                          }}
                        >
                          Resend
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setPending({ kind: "revoke", contact: c });
                          }}
                        >
                          Revoke
                        </Button>
                      </>
                    ) : (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setPending({ kind: "remove", contact: c });
                        }}
                      >
                        Remove
                      </Button>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}

      <InviteDialog
        open={inviting}
        engagementId={engagementId}
        onDone={() => {
          setInviting(false);
          refresh();
        }}
        onCancel={() => {
          setInviting(false);
        }}
      />
      <Dialog
        open={pending !== null}
        onOpenChange={(open) => {
          if (!open) setPending(null);
        }}
        title={
          pending?.kind === "remove"
            ? "Remove this contact?"
            : pending?.kind === "revoke"
              ? "Revoke this invitation?"
              : "Resend this invitation?"
        }
        description={
          pending?.kind === "remove"
            ? "They lose access to this engagement on their next request."
            : pending?.kind === "revoke"
              ? "The emailed link stops working."
              : "A new link is emailed and the previous one stops working."
        }
      >
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={() => {
              setPending(null);
            }}
          >
            Cancel
          </Button>
          <Button variant={pending?.kind === "resend" ? "default" : "danger"} onClick={confirm}>
            {pending?.kind === "remove"
              ? "Remove"
              : pending?.kind === "revoke"
                ? "Revoke"
                : "Resend"}
          </Button>
        </div>
      </Dialog>
    </section>
  );
}

function InviteDialog({
  open,
  engagementId,
  onDone,
  onCancel,
}: {
  open: boolean;
  engagementId: string;
  onDone: () => void;
  onCancel: () => void;
}): JSX.Element {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"client_admin" | "client_contributor">("client_admin");
  const invite = useMutation({
    ...inviteClientMutation(),
    onSuccess: () => {
      setEmail("");
      onDone();
    },
  });
  const submit = (event: SyntheticEvent): void => {
    event.preventDefault();
    invite.mutate({ path: { engagement_id: engagementId }, body: { email, role } });
  };
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onCancel();
      }}
      title="Invite a client contact"
      description="We email them a single-use link. You won't see the link."
    >
      <form className="flex flex-col gap-3" onSubmit={submit}>
        <div className="flex flex-col gap-1">
          <Label htmlFor="invite-email">Email</Label>
          <Input
            id="invite-email"
            type="email"
            required
            autoComplete="off"
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
            }}
          />
        </div>
        <fieldset className="flex flex-col gap-2">
          <legend className="text-sm font-semibold">Role</legend>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="invite-role"
              checked={role === "client_admin"}
              onChange={() => {
                setRole("client_admin");
              }}
            />
            Client admin: sees shared requests and invites colleagues
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="invite-role"
              checked={role === "client_contributor"}
              onChange={() => {
                setRole("client_contributor");
              }}
            />
            Contributor: works on items assigned to them
          </label>
        </fieldset>
        {invite.isError && (
          <p role="alert" className="text-sm text-danger">
            {errorMessage(invite.error)}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" disabled={invite.isPending}>
            Send invitation
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
