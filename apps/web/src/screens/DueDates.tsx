import type { RequestItemOut } from "@abacus/api-client";
import {
  defaultDueDateOptions,
  defaultDueDateQueryKey,
  dueDatesMutation,
  listRequestItemsQueryKey,
  setDefaultDueDateMutation,
} from "@abacus/api-client/query";
import { Badge, Button, Input, Label } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";

/** SPEC-027 AC-9: an item is due on its own date, else the request list's default. */
export function effectiveDue(
  item: RequestItemOut,
  fallback: string | null | undefined,
): string | null {
  return item.due_on ?? fallback ?? null;
}

/** Overdue: past its due date and still open or sent back (what the agent reminds about). */
export function isOverdue(item: RequestItemOut, due: string | null, today: string): boolean {
  return (
    due !== null && due < today && (item.status === "open" || item.status === "needs_revision")
  );
}

export function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function useDefaultDue(engagementId: string): string | null | undefined {
  const found = useQuery({
    ...defaultDueDateOptions({ path: { engagement_id: engagementId } }),
    retry: false,
  });
  return found.data?.due_on;
}

/** The request list's default due date, and setting a date on every open item without one. */
export function DueDatesBar({
  engagementId,
  items,
}: {
  engagementId: string;
  items: RequestItemOut[];
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const fallback = useDefaultDue(engagementId);
  const [value, setValue] = useState<string | null>(null);
  const shown = value ?? fallback ?? "";
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: defaultDueDateQueryKey(path) });
    void queryClient.invalidateQueries({ queryKey: listRequestItemsQueryKey(path) });
  };
  const save = useMutation({ ...setDefaultDueDateMutation(), onSuccess: refresh });
  const now = today();
  const overdue = items.filter((i) => isOverdue(i, effectiveDue(i, fallback), now)).length;
  return (
    <div className="flex flex-wrap items-end gap-3 text-sm">
      <div className="flex flex-col gap-1">
        <Label htmlFor="default-due">Due date for the request list</Label>
        <Input
          id="default-due"
          type="date"
          value={shown}
          onChange={(e) => {
            setValue(e.target.value);
          }}
        />
      </div>
      <Button
        size="sm"
        disabled={save.isPending || shown === (fallback ?? "")}
        onClick={() => {
          save.mutate({ ...path, body: { due_on: shown === "" ? null : shown } });
        }}
      >
        Save
      </Button>
      <span className="text-muted">Items without their own date are due then.</span>
      {overdue > 0 && <Badge tone="warning">{`${String(overdue)} overdue`}</Badge>}
      {save.isError && (
        <span role="alert" className="text-danger">
          {errorMessage(save.error)}
        </span>
      )}
    </div>
  );
}

/** One item's due date: its own, or the list's (shown as such), editable. */
export function ItemDue({
  item,
  fallback,
}: {
  item: RequestItemOut;
  fallback: string | null | undefined;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: item.engagement_id } };
  const save = useMutation({
    ...dueDatesMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: listRequestItemsQueryKey(path) });
    },
  });
  const due = effectiveDue(item, fallback);
  return (
    <span className="flex flex-wrap items-center gap-2">
      <Input
        aria-label={`Due date for ${item.description}`}
        type="date"
        className="h-8 w-40"
        value={item.due_on ?? ""}
        placeholder={fallback ?? ""}
        onChange={(e) => {
          save.mutate({
            ...path,
            body: { item_ids: [item.id], due_on: e.target.value === "" ? null : e.target.value },
          });
        }}
      />
      {item.due_on == null && fallback != null && (
        <span className="text-xs text-muted">{`List default: ${fallback}`}</span>
      )}
      {isOverdue(item, due, today()) && <Badge tone="warning">Overdue</Badge>}
    </span>
  );
}
