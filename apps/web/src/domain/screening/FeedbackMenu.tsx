// SHL-20 f, the thumbs (P-06-T22; ADR-068): a thumbs up records feedback at once; a thumbs down
// opens "Why?" (Wrong request match · Wrong period · Unclear file · Other, and a note), and "Send
// feedback" stays disabled until a reason is chosen (the server also answers 422 without one).
// Feedback is insert-only and the agent may never give it (`screening.feedback`, agent deny).

import type { ScreeningFeedbackIn, ScreeningFeedbackOut } from "@abacus/api-client";
import { Button, IconButton, Popover, RadioGroup, toast } from "@abacus/ui";
import { type JSX, useState } from "react";
import { SCREENING_COPY } from "./copy";

type Reason = NonNullable<ScreeningFeedbackIn["reason_code"]>;
const REASONS = Object.keys(SCREENING_COPY.feedback.reasons) as Reason[];

export interface FeedbackMenuProps {
  /** What this person already said about this aggregate. */
  given: ScreeningFeedbackOut | null;
  onSend: (body: ScreeningFeedbackIn) => Promise<unknown>;
  /** Open "Why?" as the artboard opens (f). */
  openOnMount?: boolean;
  disabled?: boolean;
}

export function FeedbackMenu({
  given,
  onSend,
  openOnMount = false,
  disabled = false,
}: FeedbackMenuProps): JSX.Element {
  const [open, setOpen] = useState(openOnMount);
  const [reason, setReason] = useState<Reason | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async (body: ScreeningFeedbackIn): Promise<void> => {
    setBusy(true);
    try {
      await onSend(body);
      setOpen(false);
      setReason(null);
      setNote("");
    } catch {
      toast.show({ kind: "error", text: SCREENING_COPY.feedback.failed });
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <IconButton
        icon="thumbs-up"
        label={SCREENING_COPY.feedback.helpful}
        variant="white"
        aria-pressed={given?.thumb === "up"}
        disabled={disabled || busy}
        onClick={() => void send({ thumb: "up" })}
      />
      <Popover
        open={open}
        onOpenChange={setOpen}
        width={266}
        align="end"
        label={SCREENING_COPY.feedback.title}
        trigger={
          <IconButton
            icon="thumbs-down"
            label={SCREENING_COPY.feedback.notHelpful}
            variant="white"
            aria-pressed={given?.thumb === "down"}
            disabled={disabled}
          />
        }
      >
        <div data-feedback-menu="" className="flex flex-col gap-[10px] p-[12px]">
          <h4 className="text-dense font-medium">{SCREENING_COPY.feedback.title}</h4>
          <RadioGroup
            label={SCREENING_COPY.feedback.title}
            options={REASONS.map((r) => ({ value: r, label: SCREENING_COPY.feedback.reasons[r] }))}
            {...(reason === null ? {} : { value: reason })}
            onChange={(v) => {
              if ((REASONS as string[]).includes(v)) setReason(v as Reason);
            }}
          />
          <textarea
            aria-label={SCREENING_COPY.feedback.note}
            placeholder={SCREENING_COPY.feedback.note}
            value={note}
            rows={2}
            maxLength={500}
            onChange={(event) => {
              setNote(event.target.value);
            }}
            className="w-full resize-none rounded-nested bg-card p-[8px] text-dense text-ink shadow-e1"
          />
          <Button
            variant="primary"
            size="sm"
            disabled={reason === null || busy}
            onClick={() => {
              if (reason === null) return;
              void send({
                thumb: "down",
                reason_code: reason,
                ...(note.trim() === "" ? {} : { note: note.trim() }),
              });
            }}
          >
            {SCREENING_COPY.feedback.send}
          </Button>
        </div>
      </Popover>
    </>
  );
}
