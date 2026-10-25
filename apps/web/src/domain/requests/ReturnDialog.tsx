// The ReturnDialog (P-06-T22; shared by SHL-20 "Return…", BND-02 g's dock "Return…" and AUD-03 d):
// a person sends one uploaded file back to the client with a reason from the platform catalogue
// (`GET …/review-reason-codes/send_back`), "Wrong document" preselected when the screening flagged
// it. The request becomes `returned` only on confirm (`POST …/decision/send-back`, human only:
// `evidence.reject`, agent deny); nothing is returned by the screening itself (INV-1).

import { reasonCodesOptions, sendBackMutation } from "@abacus/api-client/query";
import { Button, Dialog, RadioGroup, toast } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";

export const RETURN_COPY = {
  title: "Return to client",
  reason: "Reason",
  note: "Note to the client",
  confirm: "Return",
  returned: (file: string): string => `${file} returned to the client`,
  failed: "Couldn’t return the file",
} as const;

export interface ReturnTarget {
  engagementId: string;
  versionId: string;
  /** Every version to return (the request's uploads); `versionId` alone otherwise. */
  versionIds?: readonly string[];
  fileName: string;
  /** The reason to preselect: the screening's ("wrong_document"). */
  reason?: string;
}

export interface ReturnDialogProps {
  target: ReturnTarget | null;
  onClose: () => void;
  onReturned?: (versionId: string) => void;
}

export function ReturnDialog({ target, onClose, onReturned }: ReturnDialogProps): JSX.Element {
  const queryClient = useQueryClient();
  const codes = useQuery({
    ...reasonCodesOptions({
      path: { engagement_id: target?.engagementId ?? "", applies_to: "send_back" },
    }),
    enabled: target !== null,
  });
  const send = useMutation({
    ...sendBackMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        predicate: (q) => {
          const id = (q.queryKey[0] as { _id?: string } | undefined)?._id ?? "";
          return id === "screeningCard" || id === "binderRequests" || id === "getBinder";
        },
      });
    },
  });
  const [picked, setPicked] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const options = codes.data ?? [];
  const preferred = target?.reason ?? "wrong_document";
  const reason =
    picked ?? (options.some((o) => o.code === preferred) ? preferred : (options[0]?.code ?? null));
  const needsNote = options.find((o) => o.code === reason)?.requires_note === true;
  const ready = reason !== null && (!needsNote || note.trim() !== "") && !send.isPending;
  const close = (): void => {
    setPicked(null);
    setNote("");
    onClose();
  };
  const confirm = async (): Promise<void> => {
    if (target === null || reason === null) return;
    try {
      const body = { reason_code: reason, ...(note.trim() === "" ? {} : { note: note.trim() }) };
      for (const version of target.versionIds ?? [target.versionId]) {
        await send.mutateAsync({
          path: { engagement_id: target.engagementId, version_id: version },
          body,
        });
      }
      toast.show({ kind: "success", text: RETURN_COPY.returned(target.fileName) });
      onReturned?.(target.versionId);
      close();
    } catch {
      toast.show({ kind: "error", text: RETURN_COPY.failed });
    }
  };
  return (
    <Dialog
      open={target !== null}
      onOpenChange={(open) => {
        if (!open) close();
      }}
      title={RETURN_COPY.title}
      {...(target === null ? {} : { description: target.fileName })}
      dirty={note.trim() !== ""}
      action={
        <Button variant="primary" disabled={!ready} onClick={() => void confirm()}>
          {RETURN_COPY.confirm}
        </Button>
      }
    >
      <div className="flex flex-col gap-[12px]">
        {reason !== null && (
          <RadioGroup
            label={RETURN_COPY.reason}
            options={options.map((o) => ({ value: o.code, label: o.label }))}
            value={reason}
            onChange={setPicked}
          />
        )}
        <label className="flex flex-col gap-[6px] text-dense text-ink-2">
          {RETURN_COPY.note}
          <textarea
            value={note}
            rows={3}
            onChange={(event) => {
              setNote(event.target.value);
            }}
            className="w-full resize-none rounded-nested bg-card p-[10px] text-body text-ink shadow-e1"
          />
        </label>
      </div>
    </Dialog>
  );
}
