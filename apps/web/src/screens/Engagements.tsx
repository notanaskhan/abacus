import {
  createEngagementMutation,
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
  const mutation = useMutation({
    ...createEngagementMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: listEngagementsQueryKey() });
      onOpenChange(false);
    },
  });

  function submit(event: SyntheticEvent<HTMLFormElement>): void {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const field = (name: string): string => {
      const value = form.get(name);
      return typeof value === "string" ? value : "";
    };
    mutation.mutate({
      body: {
        name: field("name"),
        client_name: field("client_name"),
        client_entity_name: field("client_entity_name"),
        fiscal_period_start: field("fiscal_period_start"),
        fiscal_period_end: field("fiscal_period_end"),
        type: (field("type") || "audit") as EngagementType,
      },
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="New engagement">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <Field name="name" label="Engagement name" />
        <Field name="client_name" label="Client" />
        <Field name="client_entity_name" label="Client entity" />
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
        {mutation.isError && (
          <Alert title="Couldn't create the engagement">{errorMessage(mutation.error)}</Alert>
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
