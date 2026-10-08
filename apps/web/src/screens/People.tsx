import {
  meOptions,
  addTeamMemberMutation,
  changeTeamRoleMutation,
  removeTeamMemberMutation,
  teamCandidatesOptions,
  teamOptions,
  teamQueryKey,
} from "@abacus/api-client/query";
import { Alert, Button, Dialog, Label, Skeleton, Table, Td, Th } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type SyntheticEvent, useState } from "react";
import { errorMessage } from "../api";
import { Contacts } from "./Contacts";

type StaffRole = "engagement_partner" | "manager" | "senior" | "staff" | "reviewer";

const ROLES: { value: StaffRole; label: string }[] = [
  { value: "engagement_partner", label: "Engagement partner" },
  { value: "manager", label: "Manager" },
  { value: "senior", label: "Senior" },
  { value: "staff", label: "Staff" },
  { value: "reviewer", label: "Reviewer" },
];
const LABEL: Record<string, string> = Object.fromEntries(ROLES.map((r) => [r.value, r.label]));
// SPEC-017 Q1: managers handle seniors, staff and reviewers only.
const MANAGER_MAY: ReadonlySet<string> = new Set(["senior", "staff", "reviewer"]);

/** The engagement's people (SPEC-017 Q3): the team, then client contacts. */
export function People({ engagementId }: { engagementId: string }): JSX.Element {
  return (
    <div className="flex flex-col gap-8">
      <Team engagementId={engagementId} />
      <Contacts engagementId={engagementId} />
    </div>
  );
}

type Pending = { kind: "remove"; userId: string; name: string } | null;

function Team({ engagementId }: { engagementId: string }): JSX.Element {
  const queryClient = useQueryClient();
  const path = { engagement_id: engagementId };
  const me = useQuery(meOptions());
  const team = useQuery(teamOptions({ path }));
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: teamQueryKey({ path }) });
  };
  const change = useMutation({ ...changeTeamRoleMutation(), onSuccess: refresh });
  const remove = useMutation({ ...removeTeamMemberMutation(), onSuccess: refresh });
  const [adding, setAdding] = useState(false);
  const [pending, setPending] = useState<Pending>(null);

  const myRole = team.data?.find((m) => m.user_id === me.data?.user_id)?.role;
  const canManage = myRole === "engagement_partner" || myRole === "manager";
  const mayHandle = (role: string): boolean =>
    myRole === "engagement_partner" || (myRole === "manager" && MANAGER_MAY.has(role));
  const grantable = ROLES.filter((r) => mayHandle(r.value));
  const failed = change.error ?? remove.error;

  return (
    <section aria-labelledby="team-heading" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="team-heading" className="text-2xl">
            Team
          </h2>
          <p className="text-sm text-muted">
            Firm people working on this engagement. Their engagement role decides what they can see
            and do.
          </p>
        </div>
        {canManage && (
          <Button
            onClick={() => {
              setAdding(true);
            }}
          >
            Add person
          </Button>
        )}
      </div>
      {failed !== null && (
        <Alert title="That didn't work">
          {errorMessage(failed) === "last_partner"
            ? "An engagement needs at least one engagement partner. Add another partner first."
            : errorMessage(failed)}
        </Alert>
      )}
      {team.isPending ? (
        <Skeleton className="h-32" />
      ) : team.isError ? (
        <Alert title="Couldn't load the team">{errorMessage(team.error)}</Alert>
      ) : (
        <div className="overflow-x-auto rounded-[var(--radius-panel)] border border-line bg-surface">
          <Table className="min-w-[560px]">
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Role</Th>
                <Th>
                  <span className="sr-only">Actions</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {team.data.map((m) => (
                <tr key={m.user_id}>
                  <Td className="font-semibold">{m.display_name}</Td>
                  <Td>
                    {mayHandle(m.role) ? (
                      <label className="sr-only" htmlFor={`role-${m.user_id}`}>
                        Role for {m.display_name}
                      </label>
                    ) : null}
                    {mayHandle(m.role) ? (
                      <select
                        id={`role-${m.user_id}`}
                        value={m.role}
                        onChange={(event) => {
                          change.mutate({
                            path: { ...path, user_id: m.user_id },
                            body: { role: event.target.value as StaffRole },
                          });
                        }}
                        className="h-8 rounded-[var(--radius-control)] border border-line bg-surface px-2 text-sm"
                      >
                        {grantable.map((r) => (
                          <option key={r.value} value={r.value}>
                            {r.label}
                          </option>
                        ))}
                      </select>
                    ) : (
                      (LABEL[m.role] ?? m.role)
                    )}
                  </Td>
                  <Td className="text-right">
                    {mayHandle(m.role) && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setPending({ kind: "remove", userId: m.user_id, name: m.display_name });
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
      {adding && (
        <AddPerson
          engagementId={engagementId}
          roles={grantable}
          onClose={() => {
            setAdding(false);
          }}
          onAdded={() => {
            setAdding(false);
            refresh();
          }}
        />
      )}
      <Dialog
        open={pending !== null}
        onOpenChange={(open) => {
          if (!open) setPending(null);
        }}
        title={`Remove ${pending?.name ?? "this person"}?`}
        description="They lose access to this engagement on their next request. Reviews assigned to them here go back to the queue."
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
          <Button
            variant="danger"
            onClick={() => {
              if (pending !== null) remove.mutate({ path: { ...path, user_id: pending.userId } });
              setPending(null);
            }}
          >
            Remove
          </Button>
        </div>
      </Dialog>
    </section>
  );
}

function AddPerson({
  engagementId,
  roles,
  onClose,
  onAdded,
}: {
  engagementId: string;
  roles: { value: StaffRole; label: string }[];
  onClose: () => void;
  onAdded: () => void;
}): JSX.Element {
  const path = { engagement_id: engagementId };
  const candidates = useQuery(teamCandidatesOptions({ path }));
  const [filter, setFilter] = useState("");
  const [person, setPerson] = useState("");
  const [role, setRole] = useState<StaffRole>(roles[roles.length - 1]?.value ?? "staff");
  const add = useMutation({ ...addTeamMemberMutation(), onSuccess: onAdded });
  const shown = (candidates.data ?? []).filter((c) =>
    c.display_name.toLowerCase().includes(filter.trim().toLowerCase()),
  );
  const submit = (event: SyntheticEvent): void => {
    event.preventDefault();
    if (person !== "") add.mutate({ path, body: { user_id: person, role } });
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title="Add a person to the team"
      description="People walled off from this client, and client users, aren't listed."
    >
      <form className="flex flex-col gap-3" onSubmit={submit}>
        <div className="flex flex-col gap-1">
          <Label htmlFor="person-filter">Search people</Label>
          <input
            id="person-filter"
            type="search"
            value={filter}
            onChange={(event) => {
              setFilter(event.target.value);
            }}
            className="h-9 rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm"
          />
        </div>
        {candidates.isPending ? (
          <Skeleton className="h-24" />
        ) : candidates.isError ? (
          <p role="alert" className="text-sm text-danger">
            {errorMessage(candidates.error)}
          </p>
        ) : shown.length === 0 ? (
          <p className="text-sm text-muted">No one else can be added.</p>
        ) : (
          <fieldset className="flex max-h-56 flex-col gap-1 overflow-y-auto">
            <legend className="sr-only">Person</legend>
            {shown.map((c) => (
              <label
                key={c.user_id}
                className="flex items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-sunken"
              >
                <input
                  type="radio"
                  name="person"
                  checked={person === c.user_id}
                  onChange={() => {
                    setPerson(c.user_id);
                  }}
                />
                {c.display_name}
              </label>
            ))}
          </fieldset>
        )}
        <div className="flex flex-col gap-1">
          <Label htmlFor="person-role">Role</Label>
          <select
            id="person-role"
            value={role}
            onChange={(event) => {
              setRole(event.target.value as StaffRole);
            }}
            className="h-9 rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm"
          >
            {roles.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </div>
        {add.isError && (
          <p role="alert" className="text-sm text-danger">
            {errorMessage(add.error)}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={person === "" || add.isPending}>
            Add to team
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
