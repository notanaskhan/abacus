// QuestionCard (F-07-T06; SPEC-652 AC-5; handoff T4 ASK CARD, TPL-04a; C6 v2 wire kind `question`).
// DecisionCard's chat-ask variant: it floats above the composer (ChatThread's `above` slot), shows
// the step's question with "n of m", one radio per option with the preselected default chosen,
// and Skip, Previous and Next. Keys 1–9 choose an option, Enter is Next, Esc returns focus to the
// Composer; the composer stays live underneath. Next emits exactly one `onAnswer` with the chosen
// key; Skip emits `{skipped: true}` only when pressed (never on timeout, blur or navigation).
// "Something else…" hands the person back to the composer to type their own answer.
// It is a question to a person, never a gate: it renders no Approve, Reject, Decide, Sign off,
// Release or Send control (INV-1), and every string is the agent's, through AgentText.
import { type JSX, type KeyboardEvent, useEffect, useId, useRef, useState } from "react";
import { AgentText } from "../../agent-text";
import { Button } from "../../components/button";
import { Icon } from "../../icons";

export interface QuestionOption {
  key: string;
  title: string;
  detail?: string | null;
}

export interface QuestionStep {
  q: string;
  options: readonly QuestionOption[];
  /** Offer "Something else…" (the person types their own answer in the composer). */
  other?: boolean;
  /** The option chosen when the step opens. */
  preselect?: string | null;
}

/** The `question` item's payload, as C6 v2 carries it (SPEC-652 AC-5). */
export interface QuestionPayload {
  question_id: string;
  steps: readonly QuestionStep[];
  skipText?: string;
  skipDefault?: string | null;
  /** The step this ask opens on, 1-based, and the run's total ("1 of 2"). */
  n?: number;
  m?: number;
}

export type QuestionAnswer =
  { question_id: string; step: number; key: string } | { question_id: string; skipped: true };

export interface QuestionCardProps {
  question: QuestionPayload;
  onAnswer: (answer: QuestionAnswer) => void;
  /** "Something else…": the consumer focuses the composer for a typed answer. */
  onSomethingElse?: (question_id: string, step: number) => void;
  /** Esc: the consumer returns focus to the composer. */
  onEscape?: () => void;
  /** Answering is in flight: the controls hold, nothing is emitted twice. */
  busy?: boolean;
}

export const QUESTION_CARD_GEOMETRY = { header: 36, radio: 17, chip: 19, footerButton: 30 };
const OTHER = "Something else…";

function preselected(step: QuestionStep | undefined): string | null {
  if (step === undefined) return null;
  const wanted = step.preselect ?? null;
  if (wanted !== null && step.options.some((o) => o.key === wanted)) return wanted;
  return step.options[0]?.key ?? null;
}

function Radio({ on }: { on: boolean }): JSX.Element {
  return (
    <span
      aria-hidden="true"
      data-radio={on ? "on" : "off"}
      className={`mt-[1px] flex size-[17px] shrink-0 items-center justify-center rounded-pill ${
        on ? "bg-green text-on-dark" : "bg-card shadow-e1"
      }`}
    >
      {on ? <Icon name="check" size={12} /> : null}
    </span>
  );
}

export function QuestionCard({
  question,
  onAnswer,
  onSomethingElse,
  onEscape,
  busy = false,
}: QuestionCardProps): JSX.Element | null {
  const steps = question.steps;
  const first = Math.max(0, Math.min((question.n ?? 1) - 1, steps.length - 1));
  const [index, setIndex] = useState(first);
  const step = steps[index];
  const [chosen, setChosen] = useState<string | null>(preselected(step));
  const sent = useRef(false);
  const groupId = useId();
  const card = useRef<HTMLDivElement | null>(null);

  // A new step opens on its own default.
  useEffect(() => {
    setChosen(preselected(steps[index]));
  }, [index, steps]);

  if (step === undefined) return null;
  const total = question.m ?? steps.length;
  const at = (question.n ?? 1) + (index - first);

  const answer = (key: string) => {
    if (busy || sent.current) return;
    if (index < steps.length - 1) {
      onAnswer({ question_id: question.question_id, step: at, key });
      setIndex(index + 1);
      return;
    }
    sent.current = true;
    onAnswer({ question_id: question.question_id, step: at, key });
  };

  const next = () => {
    if (chosen !== null) answer(chosen);
  };

  const skip = () => {
    if (busy || sent.current) return;
    sent.current = true;
    onAnswer({ question_id: question.question_id, skipped: true });
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      onEscape?.();
      return;
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      next();
      return;
    }
    if (/^[1-9]$/.test(event.key)) {
      const option = step.options[Number(event.key) - 1];
      if (option !== undefined) {
        event.preventDefault();
        setChosen(option.key);
      }
    }
  };

  return (
    <div
      ref={card}
      data-kit="QuestionCard"
      data-question={question.question_id}
      data-step={at}
      role="group"
      aria-labelledby={`${groupId}-q`}
      tabIndex={-1}
      onKeyDown={onKeyDown}
      className="rounded-[12px] bg-card shadow-ask"
    >
      <div className="flex h-[36px] items-center gap-[9px] px-[14px]">
        <span
          aria-hidden="true"
          className="flex size-[19px] shrink-0 items-center justify-center rounded-pill bg-nested text-[11.5px] font-medium text-ink-2"
        >
          ?
        </span>
        <span id={`${groupId}-q`} className="min-w-0 flex-1 truncate text-[14px] font-medium">
          <AgentText text={step.q} inline className="text-[14px] text-ink" />
        </span>
        {total > 1 ? (
          <span data-stepper className="shrink-0 text-[11.5px] text-ink-3">
            {`${String(at)} of ${String(total)}`}
          </span>
        ) : null}
      </div>
      <div
        role="radiogroup"
        aria-labelledby={`${groupId}-q`}
        className="px-[14px] pt-[8px] pb-[9px]"
      >
        {step.options.map((option, i) => {
          const on = option.key === chosen;
          return (
            <label
              key={option.key}
              data-option={option.key}
              className="flex cursor-pointer gap-[10px] rounded-[8px] py-[5px]"
            >
              <input
                type="radio"
                name={groupId}
                value={option.key}
                checked={on}
                disabled={busy}
                aria-keyshortcuts={i < 9 ? String(i + 1) : undefined}
                onChange={() => {
                  setChosen(option.key);
                }}
                className="sr-only"
              />
              <Radio on={on} />
              <span className="flex min-w-0 flex-col gap-[2px]">
                <span className={`text-[13.5px] ${on ? "font-medium" : ""}`}>
                  <AgentText text={option.title} inline className="text-[13.5px] text-ink" />
                </span>
                {option.detail ? (
                  <span className="text-[12.5px] leading-[1.35] text-ink-2">
                    <AgentText text={option.detail} inline className="text-[12.5px] text-ink-2" />
                  </span>
                ) : null}
              </span>
            </label>
          );
        })}
        {step.other ? (
          <button
            type="button"
            data-option="other"
            disabled={busy}
            onClick={() => onSomethingElse?.(question.question_id, at)}
            className="flex gap-[10px] py-[5px] text-[13.5px] text-ink-2"
          >
            <Radio on={false} />
            {OTHER}
          </button>
        ) : null}
      </div>
      <div className="flex items-center gap-[8px] px-[14px] py-[8px] shadow-[inset_0_0.5px_0_rgba(43,31,23,0.10)]">
        <Button variant="secondary" size="md" disabled={busy} onClick={skip}>
          {question.skipText ?? "Skip"}
        </Button>
        <span className="flex-1" />
        <Button
          variant="secondary"
          size="md"
          disabled={busy || index === first}
          onClick={() => {
            setIndex(index - 1);
          }}
        >
          Previous
        </Button>
        <Button
          variant="primary"
          size="md"
          disabled={busy || chosen === null}
          loading={busy}
          onClick={next}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
