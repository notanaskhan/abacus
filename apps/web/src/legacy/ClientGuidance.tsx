import type { RequestItemOut } from "@abacus/api-client";
import { listRequestItemsQueryKey, setGuidanceMutation } from "@abacus/api-client/query";
import { Alert, Button, Label } from "@abacus/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";

// SPEC-031 AC-3 (TASK-061): what the client reads about this request, and how the firm plans
// it. Partner, manager and senior edit it; everyone else on the team reads it.

const LIMIT = 1000;
const KIND: Record<string, string> = {
  bank_statement: "bank statements",
  ar_aging: "AR agings",
  ap_aging: "AP agings",
  schedule: "schedules",
};
const EFFORT: Record<string, string> = {
  small: "Small, about 15 minutes",
  medium: "Medium, about 45 minutes",
  large: "Large, about 2 hours",
};

export function sourceLabel(item: RequestItemOut, approver?: string): string | null {
  switch (item.guidance_source) {
    case "drafted": // SPEC-035 (TASK-073): approved drafter text, labelled for the firm
      return `Drafted via Agent, approved by ${approver ?? "your team"}`;
    case "kind_default":
      return `Default for ${KIND[item.document_kind ?? ""] ?? "this kind of document"}`;
    case "template":
      return "From the template";
    case "firm":
      return "Written by your team";
    default:
      return null;
  }
}

type Draft = {
  why: string;
  good: string;
  still: string;
  blocks: boolean;
  effort: string;
};

function draftOf(item: RequestItemOut): Draft {
  return {
    why: item.why ?? "",
    good: item.good_looks_like ?? "",
    still: item.still_needed ?? "",
    blocks: item.blocks_fieldwork === true,
    effort: item.effort ?? "",
  };
}

function TextField({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
}): JSX.Element {
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={id}>{label}</Label>
      <textarea
        id={id}
        rows={3}
        maxLength={LIMIT}
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
        className="rounded-[var(--radius-control)] border border-hair bg-surface p-2 text-body"
      />
      <span className="text-meta text-ink-3 tabular-nums">
        {value.length} / {LIMIT}
      </span>
    </div>
  );
}

export function ClientGuidance({
  engagementId,
  item,
  canEdit,
  approver,
}: {
  engagementId: string;
  item: RequestItemOut;
  canEdit: boolean;
  approver?: string;
}): JSX.Element {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Draft | null>(null);
  const save = useMutation({
    ...setGuidanceMutation(),
    onSuccess: () => {
      setDraft(null);
      void queryClient.invalidateQueries({
        queryKey: listRequestItemsQueryKey({ path: { engagement_id: engagementId } }),
      });
    },
  });
  const source = sourceLabel(item, approver);

  if (draft === null) {
    const rows: [string, string | null | undefined][] = [
      ["Why we need it", item.why],
      ["What good looks like", item.good_looks_like],
      ["Still needed", item.still_needed],
    ];
    const written = rows.filter(([, text]) => text != null && text !== "");
    return (
      <div className="flex flex-col gap-2 text-body">
        {written.length === 0 ? (
          <p className="text-ink-3">No guidance for the client yet.</p>
        ) : (
          <dl className="flex flex-col gap-1">
            {written.map(([label, text]) => (
              <div key={label}>
                <dt className="font-medium">{label}</dt>
                <dd className="whitespace-pre-line text-ink-3">{text}</dd>
              </div>
            ))}
          </dl>
        )}
        <p className="text-meta text-ink-3">
          {item.blocks_fieldwork === true ? "Blocks fieldwork" : "Doesn't block fieldwork"} ·{" "}
          {item.effort != null ? EFFORT[item.effort] : "No estimate"}
          {source !== null && ` · ${source}`}
        </p>
        {canEdit && (
          <div>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                setDraft(draftOf(item));
              }}
            >
              Edit
            </Button>
          </div>
        )}
      </div>
    );
  }

  const set = (patch: Partial<Draft>): void => {
    setDraft({ ...draft, ...patch });
  };
  return (
    <form
      className="flex flex-col gap-3 text-body"
      aria-label="Edit client guidance"
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate({
          path: { engagement_id: engagementId, item_id: item.id },
          body: {
            why: draft.why.trim() || null,
            good_looks_like: draft.good.trim() || null,
            still_needed: draft.still.trim() || null,
            blocks_fieldwork: draft.blocks,
            effort: draft.effort === "" ? null : (draft.effort as "small" | "medium" | "large"),
          },
        });
      }}
    >
      <p className="text-meta text-ink-3">The client sees these words exactly as written.</p>
      <TextField
        id={`why-${item.id}`}
        label="Why we need it"
        value={draft.why}
        onChange={(why) => {
          set({ why });
        }}
      />
      <TextField
        id={`good-${item.id}`}
        label="What good looks like"
        value={draft.good}
        onChange={(good) => {
          set({ good });
        }}
      />
      <TextField
        id={`still-${item.id}`}
        label="Still needed"
        value={draft.still}
        onChange={(still) => {
          set({ still });
        }}
      />
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={draft.blocks}
          onChange={(event) => {
            set({ blocks: event.target.checked });
          }}
        />
        Blocks fieldwork
      </label>
      <div className="flex flex-col gap-1">
        <Label htmlFor={`effort-${item.id}`}>Effort for the client</Label>
        <select
          id={`effort-${item.id}`}
          value={draft.effort}
          onChange={(event) => {
            set({ effort: event.target.value });
          }}
          className="h-8 rounded-[var(--radius-control)] border border-hair bg-surface px-2 text-body"
        >
          <option value="">No estimate</option>
          {Object.entries(EFFORT).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <div className="flex gap-2">
        <Button size="sm" type="submit" disabled={save.isPending}>
          Save
        </Button>
        <Button
          size="sm"
          variant="ghost"
          type="button"
          onClick={() => {
            setDraft(null);
          }}
        >
          Cancel
        </Button>
      </div>
      {save.isError && (
        <Alert title="Couldn't save the guidance">{errorMessage(save.error)}</Alert>
      )}
    </form>
  );
}
