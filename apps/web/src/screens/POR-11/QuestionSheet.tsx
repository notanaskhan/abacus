// POR-11 b / POR-04 frame e (C-01-T41, DEC-5638): the question variant of the request sheet. The
// client picks one of the sheet's three choices or writes a note; the answer is sealed server-side
// (`POST /v1/portal/questions/{id}/answer`). Sending closes the sheet; the row moves to answered
// with its receipt.
import type { PortalQuestionOut } from "@abacus/api-client";
import { portalAnswerQuestionMutation } from "@abacus/api-client/query";
import { Button, Dialog } from "@abacus/ui";
import { useMutation } from "@tanstack/react-query";
import { type JSX, useId, useState } from "react";
import { COPY as C } from "./copy";

export type Choice = keyof typeof C.sheet.choices;
const CHOICES = Object.keys(C.sheet.choices) as Choice[];

export function QuestionSheet({
  question,
  onAnswered,
  onClose,
}: {
  question: PortalQuestionOut;
  onAnswered: (answered: PortalQuestionOut) => void;
  onClose: () => void;
}): JSX.Element {
  const id = useId();
  const [choice, setChoice] = useState<Choice | null>(null);
  const [note, setNote] = useState("");
  const send = useMutation({ ...portalAnswerQuestionMutation(), onSuccess: onAnswered });
  const ready = choice !== null || note.trim() !== "";
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={C.sheet.title}
      action={
        <Button
          variant="primary"
          disabled={!ready || send.isPending}
          onClick={() => {
            send.mutate({
              path: { question_id: question.question_id },
              headers: { "Idempotency-Key": `por11-${question.question_id}-${crypto.randomUUID()}` },
              body: { choice, note: note.trim() === "" ? null : note.trim() },
            });
          }}
        >
          {C.sheet.send}
        </Button>
      }
    >
      <div data-por11="sheet" className="flex flex-col gap-[10px] p-[16px]">
        <p className="text-[13.5px] font-medium">{question.client_wording}</p>
        <p className="text-[12.5px] text-ink-2">{question.context_line}</p>
        <fieldset className="flex flex-col gap-[6px]">
          <legend className="sr-only">{C.sheet.title}</legend>
          {CHOICES.map((c) => (
            <label key={c} className="flex h-[36px] items-center gap-[8px] text-[13px]">
              <input
                type="radio"
                name={`${id}-choice`}
                checked={choice === c}
                onChange={() => {
                  setChoice(c);
                }}
              />
              {C.sheet.choices[c]}
            </label>
          ))}
        </fieldset>
        <label htmlFor={`${id}-note`} className="text-[12.5px] text-ink-2">
          {C.sheet.note}
        </label>
        <textarea
          id={`${id}-note`}
          value={note}
          maxLength={2000}
          onChange={(e) => {
            setNote(e.target.value);
          }}
          className="min-h-[72px] rounded-input bg-card p-[8px] text-cell inset-ring-[0.5px] inset-ring-stroke"
        />
      </div>
    </Dialog>
  );
}
