import {
  activityQueryKey,
  dismissDraftMutation,
  draftsOptions,
  draftsQueryKey,
  sendDraftMutation,
} from "@abacus/api-client/query";
import type { DraftOut } from "@abacus/api-client";
import { Button, Input, Panel } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";

/** SPEC-027 AC-4: at Advise, the reminders the agent drafted, for a person to send or dismiss. */
export function ReminderDrafts({ engagementId }: { engagementId: string }): JSX.Element | null {
  const path = { path: { engagement_id: engagementId } };
  const drafts = useQuery({ ...draftsOptions(path), retry: false });
  if (drafts.data === undefined || drafts.data.length === 0) return null;
  return (
    <Panel title="Reminders waiting for you">
      <ul className="flex flex-col divide-y divide-line">
        {drafts.data.map((d) => (
          <DraftRow key={d.id} engagementId={engagementId} draft={d} />
        ))}
      </ul>
    </Panel>
  );
}

function DraftRow({
  engagementId,
  draft,
}: {
  engagementId: string;
  draft: DraftOut;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId, reminder_id: draft.id } };
  const [note, setNote] = useState("");
  const done = (): void => {
    const engagement = { path: { engagement_id: engagementId } };
    void queryClient.invalidateQueries({ queryKey: draftsQueryKey(engagement) });
    void queryClient.invalidateQueries({ queryKey: activityQueryKey(engagement) });
  };
  const send = useMutation({ ...sendDraftMutation(), onSuccess: done });
  const dismiss = useMutation({ ...dismissDraftMutation(), onSuccess: done });
  const busy = send.isPending || dismiss.isPending;
  return (
    <li className="flex flex-col gap-2 py-3 text-sm">
      <p className="font-medium">To {draft.recipient_name || "a client contact"}</p>
      <ul className="list-disc pl-5 text-muted">
        {draft.items.map((i) => (
          <li key={i.request_item_id}>{i.description}</li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          aria-label={`A note for ${draft.recipient_name || "the client contact"} (optional)`}
          maxLength={500}
          placeholder="Add a note (optional)"
          value={note}
          onChange={(e) => {
            setNote(e.target.value);
          }}
        />
        <Button
          size="sm"
          disabled={busy}
          onClick={() => {
            send.mutate({ ...path, body: note.trim() === "" ? {} : { note } });
          }}
        >
          Send
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={busy}
          onClick={() => {
            dismiss.mutate(path);
          }}
        >
          Dismiss
        </Button>
      </div>
      {(send.isError || dismiss.isError) && (
        <p role="alert" className="text-danger">
          {errorMessage(send.error ?? dismiss.error)}
        </p>
      )}
    </li>
  );
}
