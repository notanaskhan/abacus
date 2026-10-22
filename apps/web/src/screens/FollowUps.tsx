import type { DraftOut } from "@abacus/api-client";
import {
  activityQueryKey,
  dismissDraftMutation,
  draftFollowUpsMutation,
  draftsOptions,
  draftsQueryKey,
  previewFollowUpMutation,
  sendDraftMutation,
} from "@abacus/api-client/query";
import {
  Button,
  type Column,
  DataTable,
  DateText,
  EmptyState,
  Fieldset,
  Sheet,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useEffect, useState } from "react";
import { errorMessage } from "../api";

// Follow-ups (TASK-104; the plan's P-06-T14, DEC-74): the agent drafts one follow-up per client
// contact for their overdue items; a person reads the exact email (a fixed template, never model
// text), adds a note if they like, and sends it with ten seconds to undo.

const SAID: Record<string, string> = {
  engagement_not_open: "Nothing goes to the client before the engagement is open.",
  follow_up_gone: "Someone already sent or dismissed this follow-up.",
};

function said(error: unknown): string {
  return SAID[errorMessage(error)] ?? "That didn't work. Try again.";
}

export function FollowUps({ engagementId }: { engagementId: string }): JSX.Element | null {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const drafts = useQuery({ ...draftsOptions(path), retry: false });
  const [open, setOpen] = useState<DraftOut | null>(null);
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: draftsQueryKey(path) });
    void queryClient.invalidateQueries({ queryKey: activityQueryKey(path) });
  };
  const draftNow = useMutation({
    ...draftFollowUpsMutation(),
    onSuccess: (data) => {
      refresh();
      toast.show(
        data.drafted === 0
          ? "Nothing new to follow up"
          : `${String(data.drafted)} follow-up${data.drafted === 1 ? "" : "s"} drafted`,
      );
    },
  });
  if (drafts.isError) return null; // not for this role
  const rows = drafts.data ?? [];
  const columns: Column<DraftOut>[] = [
    {
      key: "to",
      header: "To",
      cell: (d) => <span className="font-medium">{d.recipient_name || "A client contact"}</span>,
      sortValue: (d) => d.recipient_name,
    },
    {
      key: "items",
      header: "Overdue items",
      cell: (d) => (
        <span className="text-ink-2">
          {d.items[0]?.description}
          {d.items.length > 1 && (
            <span className="text-ink-3">{` and ${String(d.items.length - 1)} more`}</span>
          )}
        </span>
      ),
      sortValue: (d) => d.items.length,
    },
    {
      key: "when",
      header: "Drafted",
      cell: (d) => <DateText value={d.created_at} className="text-ink-3" />,
      sortValue: (d) => d.created_at,
    },
    {
      key: "open",
      header: <span className="sr-only">Review</span>,
      align: "right",
      width: "w-[130px]",
      cell: (d) => (
        <Button
          size="sm"
          variant="secondary"
          onClick={(e) => {
            e.stopPropagation();
            setOpen(d);
          }}
        >
          Review and send
        </Button>
      ),
    },
  ];
  return (
    <section
      aria-labelledby="follow-ups-heading"
      className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2"
    >
      <div className="flex min-h-[50px] flex-wrap items-center gap-2 border-b-[0.5px] border-hair px-4 py-2">
        <h2 id="follow-ups-heading" className="text-[15px] font-medium tracking-[-0.012em]">
          Follow-ups
        </h2>
        <span className="text-[12.5px] text-ink-3 tabular-nums">{rows.length}</span>
        <span className="flex-1" />
        {draftNow.isError && <span className="text-meta text-danger">{said(draftNow.error)}</span>}
        <Button
          size="sm"
          variant="secondary"
          disabled={draftNow.isPending}
          onClick={() => {
            draftNow.mutate(path);
          }}
        >
          Draft follow-ups for overdue items
        </Button>
      </div>
      {rows.length === 0 ? (
        <EmptyState title="No follow-ups waiting">
          The agent drafts one per client contact when items go overdue. You read and send each.
        </EmptyState>
      ) : (
        <DataTable
          label="Follow-ups waiting to be sent"
          rows={rows}
          columns={columns}
          rowKey={(d) => d.id}
          onRowClick={setOpen}
        />
      )}
      {open !== null && (
        <SendSheet
          engagementId={engagementId}
          draft={open}
          onClose={() => {
            setOpen(null);
          }}
          onSettled={refresh}
        />
      )}
    </section>
  );
}

function SendSheet({
  engagementId,
  draft,
  onClose,
  onSettled,
}: {
  engagementId: string;
  draft: DraftOut;
  onClose: () => void;
  onSettled: () => void;
}): JSX.Element {
  const path = { path: { engagement_id: engagementId, follow_up_id: draft.id } };
  const [note, setNote] = useState("");
  const preview = useMutation(previewFollowUpMutation());
  const send = useMutation({ ...sendDraftMutation(), onSettled });
  const dismiss = useMutation({
    ...dismissDraftMutation(),
    onSuccess: () => {
      onSettled();
      onClose();
      toast.show("Follow-up dismissed");
    },
  });
  const show = preview.mutate;
  useEffect(() => {
    show({ ...path, body: {} });
  }, [draft.id]);
  const to = draft.recipient_name || "the client contact";
  return (
    <Sheet
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={`Follow-up to ${to}`}
      description="Sent from your firm's template. Nothing goes until you send it, and you have ten seconds to undo."
      footer={
        <>
          <Button
            variant="ghost"
            disabled={dismiss.isPending}
            onClick={() => {
              dismiss.mutate(path);
            }}
          >
            Dismiss
          </Button>
          <Button
            onClick={() => {
              const body = note.trim() === "" ? {} : { note };
              onClose();
              toast.deferred(`Follow-up to ${to} sent`, () => {
                send.mutate({ ...path, body });
              });
            }}
          >
            Send
          </Button>
        </>
      }
    >
      <Fieldset title="Email">
        {preview.isPending && <p className="text-[12.5px] text-ink-3">Preparing the preview…</p>}
        {preview.isError && <p className="text-meta text-danger">{said(preview.error)}</p>}
        {preview.data !== undefined && (
          <div className="flex flex-col gap-2">
            <p className="text-[13px] font-medium">{preview.data.subject}</p>
            <pre className="font-ui text-[12.5px] leading-[1.55] whitespace-pre-wrap text-ink-2">
              {preview.data.body}
            </pre>
          </div>
        )}
      </Fieldset>
      <Fieldset title="Add a note (optional)">
        <textarea
          aria-label={`A note for ${to} (optional)`}
          value={note}
          maxLength={500}
          onChange={(e) => {
            setNote(e.target.value);
          }}
          onBlur={() => {
            show({ ...path, body: note.trim() === "" ? {} : { note } });
          }}
          placeholder="Written by you; it appears above the link"
          className="min-h-[64px] w-full rounded-tile border-0 bg-nested p-2.5 text-[13px] inset-shadow-hair focus:bg-card"
        />
      </Fieldset>
      {(send.isError || dismiss.isError) && (
        <p role="alert" className="text-meta text-danger">
          {said(send.error ?? dismiss.error)}
        </p>
      )}
    </Sheet>
  );
}
