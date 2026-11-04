import {
  approvalBatchUndoMutation,
  proposedEntriesSendMutation,
  proposedEntriesSendPreviewOptions,
} from "@abacus/api-client/query";
import { Amount, Button, Dialog, Skeleton } from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import { type JSX, useState } from "react";
import type { OverlayRenderProps } from "../../app-core/overlays";
import { COPY } from "./copy";

// AUD-16 O3 · Send to client (A-06-T22; C8, DEC-24, DEC-79): `?ov=send-entries:<entryId>…` over the
// audit. The sheet shows the recipient and, per entry, the firm template's client wording from the
// server's preview (database content, never a model's), then approves and sends in one call
// (`proposed_entry.send_to_client`, fresh MFA). For 10 seconds the client sees nothing: Undo calls
// only the compensating command (`POST /approval-batches/{id}/undo`).

function idempotency(): { "Idempotency-Key": string } {
  return { "Idempotency-Key": crypto.randomUUID() };
}

export function SendEntriesBody({
  workItemId,
  entryIds,
  onDone,
}: {
  workItemId: string;
  entryIds: readonly string[];
  onDone: () => void;
}): JSX.Element {
  const preview = useQuery({
    ...proposedEntriesSendPreviewOptions({
      path: { work_item_id: workItemId },
      query: { entry_ids: [...entryIds] },
    }),
    enabled: entryIds.length > 0,
  });
  const [batch, setBatch] = useState<string | null>(null);
  const [undone, setUndone] = useState(false);
  const send = useMutation({
    ...proposedEntriesSendMutation(),
    onSuccess: (out) => {
      setBatch(out.approval_batch_id);
    },
  });
  const undo = useMutation({
    ...approvalBatchUndoMutation(),
    onSuccess: () => {
      setUndone(true);
    },
  });
  const p = preview.data;
  if (p === undefined) return <Skeleton className="h-[120px]" />;
  return (
    <div data-aud16="send" className="flex flex-col gap-[10px]">
      <p className="text-dense">{COPY.send.to(p.recipient_name)}</p>
      <p className="text-meta text-ink-3">{COPY.send.template(p.template_label)}</p>
      <ul className="flex flex-col gap-[8px]">
        {p.entries.map((e) => (
          <li key={e.id} data-send-entry={e.ref} className="rounded-nested bg-nested p-[10px]">
            <div className="flex items-center justify-between text-dense font-medium">
              <span>{e.ref}</span>
              <Amount value={e.amount} style="whole" />
            </div>
            <p data-client-wording className="pt-[4px] text-dense text-ink-2">
              {e.client_wording}
            </p>
          </li>
        ))}
      </ul>
      {send.isError && (
        <p role="alert" className="text-dense text-red-ink">
          {COPY.send.refused}
        </p>
      )}
      {batch === null ? (
        <div className="flex justify-end gap-[8px]">
          <Button variant="secondary" size="sm" onClick={onDone}>
            {COPY.send.cancel}
          </Button>
          <Button
            variant="primary"
            size="sm"
            disabled={send.isPending}
            onClick={() => {
              send.mutate({
                path: { work_item_id: workItemId },
                body: {
                  entry_ids: p.entries.map((e) => e.id),
                  recipient_contact_id: p.recipient_contact_id,
                  wording_template_version_id: p.wording_template_version_id,
                  seen_versions: p.seen_versions,
                },
                headers: idempotency(),
              });
            }}
          >
            {COPY.send.send}
          </Button>
        </div>
      ) : (
        <div data-aud16="sent" className="flex items-center justify-between gap-[8px] text-dense">
          <span>{undone ? COPY.send.undone : COPY.send.sent}</span>
          {!undone && (
            <Button
              variant="secondary"
              size="sm"
              disabled={undo.isPending}
              onClick={() => {
                undo.mutate({
                  path: { batch_id: batch },
                  query: { work_item_id: workItemId },
                  headers: idempotency(),
                });
              }}
            >
              {COPY.send.undo}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

export function SendEntriesSheet({ ref, close }: OverlayRenderProps): JSX.Element {
  const params: { auditId?: string } = useParams({ strict: false });
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) close();
      }}
      title={COPY.send.title}
    >
      <SendEntriesBody workItemId={params.auditId ?? ""} entryIds={ref.args} onDone={close} />
    </Dialog>
  );
}
