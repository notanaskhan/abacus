import type { WallOut } from "@abacus/api-client";
import {
  createWallMutation,
  firmClientsOptions,
  firmMembersOptions,
  listWallsOptions,
  listWallsQueryKey,
  removeWallMutation,
} from "@abacus/api-client/query";
import { Alert, Button, Dialog, Label, Panel, Skeleton, Table, Td, Th } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type SyntheticEvent, useEffect, useState } from "react";
import { errorMessage } from "../api";
import { ConfirmItsYou, isForbidden } from "../shell/mfa";

const REFUSALS: Record<string, string> = {
  wall_exists: "That person is already walled off from this client.",
  own_wall: "You can't lift a wall on yourself. Another firm admin must remove it.",
};

function refusal(error: unknown): string {
  const code = errorMessage(error);
  return REFUSALS[code] ?? code;
}

const SELECT = "h-9 rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm";

/** SPEC-019 AC-6: ethical walls. Listing needs a recent sign-in, so the prompt comes first. */
export function Walls(): JSX.Element {
  const walls = useQuery(listWallsOptions());
  const [confirm, setConfirm] = useState(false);
  const forbidden = walls.isError && isForbidden(walls.error);
  useEffect(() => {
    if (forbidden) setConfirm(true);
  }, [forbidden]);

  return (
    <div className="flex flex-col gap-4">
      {walls.isPending ? (
        <Skeleton className="h-32" />
      ) : walls.isError ? (
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
            Walls need a recent sign-in. If it still isn&apos;t allowed, your role doesn&apos;t
            permit it.
          </Alert>
        ) : (
          <Alert title="Couldn't load walls">{errorMessage(walls.error)}</Alert>
        )
      ) : (
        <WallList walls={walls.data} onForbidden={setConfirm} />
      )}
      <ConfirmItsYou open={confirm} onOpenChange={setConfirm} />
    </div>
  );
}

function WallList({
  walls,
  onForbidden,
}: {
  walls: WallOut[];
  onForbidden: (open: boolean) => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const members = useQuery(firmMembersOptions());
  const clients = useQuery(firmClientsOptions());
  const [userId, setUserId] = useState("");
  const [clientId, setClientId] = useState("");
  const [removing, setRemoving] = useState<WallOut | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: listWallsQueryKey() });
  };
  const onError = (error: unknown): void => {
    if (isForbidden(error)) onForbidden(true);
    else setFailure(refusal(error));
  };
  const create = useMutation({
    ...createWallMutation(),
    onSuccess: () => {
      setUserId("");
      setClientId("");
      setFailure(null);
      refresh();
    },
    onError,
  });
  const remove = useMutation({
    ...removeWallMutation(),
    onSuccess: () => {
      setRemoving(null);
      setFailure(null);
      refresh();
    },
    onError: (error) => {
      setRemoving(null);
      onError(error);
    },
  });

  const people = new Map((members.data ?? []).map((m) => [m.user_id, m.display_name]));
  const names = new Map((clients.data ?? []).map((c) => [c.client_id, c.name]));
  const person = (id: string): string => people.get(id) ?? `Person ${id.slice(0, 8)}`;
  const client = (id: string): string => names.get(id) ?? `Client ${id.slice(0, 8)}`;
  const active = walls.filter((w) => w.status === "active");

  const submit = (event: SyntheticEvent): void => {
    event.preventDefault();
    if (userId === "" || clientId === "") return;
    create.mutate({ body: { user_id: userId, client_id: clientId } });
  };

  return (
    <>
      <Panel title="Add a wall">
        <form className="flex flex-wrap items-end gap-3" onSubmit={submit}>
          <div className="flex flex-col gap-1">
            <Label htmlFor="wall-person">Person</Label>
            <select
              id="wall-person"
              className={SELECT}
              value={userId}
              onChange={(event) => {
                setUserId(event.target.value);
              }}
            >
              <option value="">Choose a person…</option>
              {(members.data ?? []).map((m) => (
                <option key={m.user_id} value={m.user_id}>
                  {m.display_name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="wall-client">Client</Label>
            <select
              id="wall-client"
              className={SELECT}
              value={clientId}
              onChange={(event) => {
                setClientId(event.target.value);
              }}
            >
              <option value="">Choose a client…</option>
              {(clients.data ?? []).map((c) => (
                <option key={c.client_id} value={c.client_id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <Button type="submit" disabled={userId === "" || clientId === "" || create.isPending}>
            Add wall
          </Button>
        </form>
        {failure !== null && (
          <p role="alert" className="text-sm text-danger">
            {failure}
          </p>
        )}
      </Panel>
      <Panel title="Walls in place">
        {active.length === 0 ? (
          <p className="text-sm text-muted">No walls. Everyone can be staffed on any client.</p>
        ) : (
          <div className="overflow-x-auto">
            <Table className="min-w-[520px]">
              <thead>
                <tr>
                  <Th>Person</Th>
                  <Th>Client</Th>
                  <Th>Since</Th>
                  <Th>
                    <span className="sr-only">Actions</span>
                  </Th>
                </tr>
              </thead>
              <tbody>
                {active.map((w) => (
                  <tr key={w.id}>
                    <Td>{person(w.user_id)}</Td>
                    <Td>{client(w.client_id)}</Td>
                    <Td className="tabular-nums">{new Date(w.created_at).toLocaleDateString()}</Td>
                    <Td>
                      <Button
                        size="sm"
                        variant="danger"
                        onClick={() => {
                          setRemoving(w);
                        }}
                      >
                        Remove
                      </Button>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}
      </Panel>
      <Dialog
        open={removing !== null}
        onOpenChange={(next) => {
          if (!next) setRemoving(null);
        }}
        title="Remove wall"
        description={
          removing === null
            ? ""
            : `${person(removing.user_id)} could then be staffed on ${client(removing.client_id)}.`
        }
      >
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={() => {
              setRemoving(null);
            }}
          >
            Cancel
          </Button>
          <Button
            variant="danger"
            disabled={remove.isPending}
            onClick={() => {
              if (removing !== null) remove.mutate({ path: { wall_id: removing.id } });
            }}
          >
            Remove
          </Button>
        </div>
      </Dialog>
    </>
  );
}
