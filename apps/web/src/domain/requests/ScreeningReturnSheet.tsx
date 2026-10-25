// SHL-20 b, the screening-return follow-up (P-06-T22; DV-1): an O3 sheet over the card, "Follow-up
// to Luis Ferrante". The platform drafted it from the firm's Return template (file names, reason
// labels, request title, signer; never model text, DEC-79), so it carries the C-31 tag "Drafted
// by Accrued Agent · edit before sending". The person edits it and sends it: "Send to …" is theirs
// (`follow_up.send`, agent deny) with ten seconds to Undo (ADR-161). The to-do checkbox renders
// only once `todo.create` exists (P-05; DV-1), so not here.

import type { FollowUpOut } from "@abacus/api-client";
import { Button, Icon, SheetModal, toast } from "@abacus/ui";
import { type JSX, useState } from "react";
import { SCREENING_COPY } from "../screening/copy";
import { shortName } from "../screening/compose";

export interface ScreeningReturnSheetProps {
  draft: FollowUpOut | null;
  /** The files it returns, by name ("Returning: …"). */
  returning: readonly string[];
  onEdit: (body: string) => Promise<FollowUpOut>;
  onSend: () => Promise<FollowUpOut>;
  onUndo: () => Promise<FollowUpOut>;
  onClose: () => void;
  sending?: boolean;
}

export function ScreeningReturnSheet({
  draft,
  returning,
  onEdit,
  onSend,
  onUndo,
  onClose,
  sending = false,
}: ScreeningReturnSheetProps): JSX.Element {
  const [text, setText] = useState<string | null>(null);
  const body = text ?? draft?.body ?? "";
  const name = draft?.recipient_name ?? "";
  const request = draft?.items[0]?.title ?? "";
  const close = (): void => {
    setText(null);
    onClose();
  };
  const send = async (): Promise<void> => {
    if (draft === null) return;
    try {
      const next = body.trim();
      if (next !== "" && next !== draft.body) await onEdit(next);
      await onSend();
      close();
      toast.undoable({
        text: SCREENING_COPY.sheet.sent(name),
        undo: () => {
          void onUndo();
        },
      });
    } catch {
      toast.show({ kind: "error", text: SCREENING_COPY.sheet.sendFailed });
    }
  };
  return (
    <SheetModal
      open={draft !== null}
      onOpenChange={(open) => {
        if (!open) close();
      }}
      title={SCREENING_COPY.sheet.title(name)}
      description={SCREENING_COPY.sheet.context(shortName(request))}
      dirty={text !== null && text !== draft?.body}
      footer={
        <div className="flex w-full items-center gap-[8px]">
          <span className="text-meta text-ink-3">
            {SCREENING_COPY.sheet.footnote(returning.length)}
          </span>
          <span className="ml-auto flex items-center gap-[8px]">
            <Button variant="secondary" size="md" onClick={close}>
              {SCREENING_COPY.sheet.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={draft === null || sending || body.trim() === ""}
              onClick={() => void send()}
            >
              {SCREENING_COPY.sheet.send(name)}
            </Button>
          </span>
        </div>
      }
    >
      <div data-screening-return="" className="flex flex-col gap-[10px]">
        <p className="flex w-fit items-center gap-[6px] rounded-pill bg-nested px-[8px] py-[3px] text-meta text-ink-2">
          <Icon name="atom" size={12} aria-hidden />
          {SCREENING_COPY.sheet.tag}
        </p>
        <textarea
          aria-label={SCREENING_COPY.sheet.body(name)}
          value={body}
          rows={9}
          onChange={(event) => {
            setText(event.target.value);
          }}
          className="w-full resize-none rounded-nested bg-card p-[12px] text-body leading-[1.5] text-ink shadow-e1"
        />
        <ul className="flex flex-wrap gap-[6px]">
          {returning.map((file) => (
            <li
              key={file}
              className="inline-flex h-[24px] items-center rounded-pill bg-card px-[10px] text-meta text-ink-2 shadow-e1"
            >
              {SCREENING_COPY.sheet.returning(file)}
            </li>
          ))}
        </ul>
      </div>
    </SheetModal>
  );
}
