import type { ClientChoiceOut } from "@abacus/api-client";
import {
  createEngagementMutation,
  searchClientsOptions,
  listEngagementsOptions,
  listEngagementsQueryKey,
} from "@abacus/api-client/query";
import {
  Alert,
  Badge,
  Button,
  Dialog,
  EmptyState,
  Input,
  Label,
  Skeleton,
  Table,
  Td,
  Th,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type SyntheticEvent, type JSX, useState } from "react";
import { errorMessage } from "../api";
import { Onboarding } from "./Onboarding";
import { type EngagementType, ENGAGEMENT_TYPES, typeLabel } from "./engagementTypes";

export function Engagements(): JSX.Element {
  const engagements = useQuery(listEngagementsOptions());
  const [creating, setCreating] = useState(false);
  const create = (
    <Button
      onClick={() => {
        setCreating(true);
      }}
    >
      New engagement
    </Button>
  );

  return (
    <section aria-labelledby="engagements-heading" className="flex flex-col gap-4">
      <Onboarding />
      <div className="flex items-center justify-between">
        <h1 id="engagements-heading" className="text-xl font-semibold">
          Engagements
        </h1>
        {create}
      </div>
      {engagements.isPending ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="h-8" />
          <Skeleton className="h-8" />
          <Skeleton className="h-8" />
        </div>
      ) : engagements.isError ? (
        <Alert
          title="Couldn't load engagements"
          action={
            <Button size="sm" variant="outline" onClick={() => void engagements.refetch()}>
              Retry
            </Button>
          }
        >
          {errorMessage(engagements.error)}
        </Alert>
      ) : engagements.data.length === 0 ? (
        <EmptyState title="No engagements yet" action={create}>
          Create one to start requesting evidence.
        </EmptyState>
      ) : (
        <Table>
          <thead>
            <tr>
              <Th>Engagement</Th>
              <Th>Client</Th>
              <Th>Fiscal period</Th>
              <Th>Status</Th>
            </tr>
          </thead>
          <tbody>
            {engagements.data.map((e) => (
              <tr key={e.id}>
                <Td>
                  <Link
                    to="/engagements/$engagementId"
                    params={{ engagementId: e.id }}
                    className="font-medium underline-offset-2 hover:underline"
                  >
                    {e.name}
                  </Link>
                </Td>
                <Td>
                  {e.client_name} — {e.client_entity_name}
                  <span className="block text-xs text-muted">{typeLabel(e.type)}</span>
                </Td>
                <Td>
                  {e.fiscal_period_start} to {e.fiscal_period_end}
                </Td>
                <Td>
                  <Badge tone={e.status === "active" ? "success" : "neutral"}>{e.status}</Badge>
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <CreateEngagement open={creating} onOpenChange={setCreating} />
    </section>
  );
}

function CreateEngagement({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const [picked, setPicked] = useState<ClientChoiceOut | null>(null);
  const [entity, setEntity] = useState<string>("");
  const [confirmNew, setConfirmNew] = useState(false);
  const mutation = useMutation({
    ...createEngagementMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: listEngagementsQueryKey() });
      onOpenChange(false);
    },
  });
  const duplicate = mutation.isError && errorMessage(mutation.error) === "possible_duplicate";

  function submit(event: SyntheticEvent<HTMLFormElement>): void {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const field = (name: string): string => {
      const value = form.get(name);
      return typeof value === "string" ? value : "";
    };
    const chosenEntity = picked?.entities.find((e) => e.id === entity);
    mutation.mutate({
      body: {
        name: field("name"),
        client_name: picked?.name ?? field("client_name"),
        client_entity_name: chosenEntity?.name ?? field("client_entity_name"),
        fiscal_period_start: field("fiscal_period_start"),
        fiscal_period_end: field("fiscal_period_end"),
        type: (field("type") || "audit") as EngagementType,
        // SPEC-025 AC-1: a client the firm already has, picked rather than typed again.
        ...(picked !== null ? { client_id: picked.id } : {}),
        ...(chosenEntity !== undefined ? { client_entity_id: chosenEntity.id } : {}),
        ...(confirmNew ? { confirm_new: true } : {}),
      },
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="New engagement">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <ClientPicker
          picked={picked}
          onPick={(client) => {
            setPicked(client);
            setEntity(client?.entities[0]?.id ?? "");
            setConfirmNew(false);
          }}
        />
        {picked === null ? (
          <>
            <Field name="client_name" label="Client" />
            <Field name="client_entity_name" label="Client entity" />
          </>
        ) : (
          <div className="flex flex-col gap-1">
            <Label htmlFor="entity">Client entity</Label>
            <select
              id="entity"
              value={entity}
              onChange={(event) => {
                setEntity(event.target.value);
              }}
              className="h-9 rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm"
            >
              {picked.entities.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                </option>
              ))}
              <option value="">Add an entity…</option>
            </select>
            {entity === "" && <Field name="client_entity_name" label="New entity name" />}
          </div>
        )}
        <Field name="name" label="Engagement name" />
        <div className="flex flex-col gap-1">
          <Label htmlFor="type">Engagement type</Label>
          <select
            id="type"
            name="type"
            defaultValue="audit"
            className="h-9 rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm"
          >
            {ENGAGEMENT_TYPES.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field name="fiscal_period_start" label="Fiscal year start" type="date" />
          <Field name="fiscal_period_end" label="Fiscal year end" type="date" />
        </div>
        {duplicate && !confirmNew ? (
          <Alert title="This client may already exist">
            Find it with the search above and pick it, so its walls and history carry over. If it
            really is a different client,{" "}
            <button
              type="button"
              className="font-semibold text-accent hover:underline"
              onClick={() => {
                setConfirmNew(true);
              }}
            >
              create a new client anyway
            </button>
            .
          </Alert>
        ) : (
          mutation.isError &&
          !duplicate && (
            <Alert title="Couldn't create the engagement">{errorMessage(mutation.error)}</Alert>
          )
        )}
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Creating…" : "Create engagement"}
        </Button>
      </form>
    </Dialog>
  );
}

function Field({
  name,
  label,
  type = "text",
}: {
  name: string;
  label: string;
  type?: string;
}): JSX.Element {
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={name}>{label}</Label>
      <Input id={name} name={name} type={type} required />
    </div>
  );
}

/** SPEC-025 AC-1: find a client the firm already has (walled clients are never listed). */
function ClientPicker({
  picked,
  onPick,
}: {
  picked: ClientChoiceOut | null;
  onPick: (client: ClientChoiceOut | null) => void;
}): JSX.Element {
  const [text, setText] = useState("");
  const found = useQuery({
    ...searchClientsOptions({ query: { q: text.trim() } }),
    enabled: text.trim().length >= 2 && picked === null,
    retry: false,
  });
  if (picked !== null) {
    return (
      <div className="flex items-center justify-between rounded-[var(--radius-control)] border border-line bg-sunken px-3 py-2 text-sm">
        <span>
          Client: <span className="font-semibold">{picked.name}</span>
        </span>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            onPick(null);
            setText("");
          }}
        >
          Change
        </Button>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor="client-search">Find an existing client</Label>
      <Input
        id="client-search"
        type="search"
        placeholder="Start typing a client's name"
        value={text}
        onChange={(event) => {
          setText(event.target.value);
        }}
      />
      {found.data !== undefined && found.data.length > 0 && (
        <ul aria-label="Matching clients" className="flex flex-col gap-1">
          {found.data.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                className="w-full rounded-[var(--radius-control)] border border-line px-3 py-1.5 text-left text-sm hover:bg-sunken"
                onClick={() => {
                  onPick(c);
                }}
              >
                {c.name}
                <span className="text-muted">
                  {" "}
                  · {c.entities.length} {c.entities.length === 1 ? "entity" : "entities"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {found.data !== undefined && found.data.length === 0 && (
        <p className="text-xs text-muted">No match. Enter a new client below.</p>
      )}
    </div>
  );
}
