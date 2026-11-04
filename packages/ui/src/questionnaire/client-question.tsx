import type { JSX } from "react";
import { cn } from "../cn";

// The client's question renderer (T-03-T09; POR-05's grammar, T7): one question as the portal
// draws it — the wording, Yes / No pills, amount rows, the upload link and its Ignore pill — and
// nothing of the firm's: no tags, banners, helpers or Required toggles, only a small "Required"
// marker when the question is required. BND-03's preview dock renders it; POR-05 moves onto it
// with T-03-T10. Read-only: a preview never answers.

export type ClientQuestionType =
  "yes_no" | "amount" | "choice" | "date" | "text" | "upload_if_yes";

export interface ClientQuestion {
  key: string;
  wording: string;
  type: ClientQuestionType;
  required: boolean;
  /** The client's answer as the portal stores it; booleans for Yes / No. */
  answer?: unknown;
  choices?: readonly string[];
  /** Amount rows ("Federal", "New York"). */
  amountParts?: readonly string[];
}

export interface ClientQuestionPreviewProps {
  question: ClientQuestion;
  /** Its visible follow-ups, drawn under it. */
  followUps?: readonly ClientQuestion[];
  className?: string;
}

const PILL = "flex h-[30px] items-center rounded-full px-[14px] text-[13px]";

function answerText(v: unknown): string {
  if (typeof v === "string") return v;
  if (typeof v === "number") return String(v);
  return "";
}

function Body({ q }: { q: ClientQuestion }): JSX.Element | null {
  if (q.type === "yes_no" || q.type === "upload_if_yes") {
    const yes = q.answer === true || q.answer === "Yes";
    const no = q.answer === false || q.answer === "No";
    if (q.type === "upload_if_yes" && yes) return null;
    return (
      <div className="flex gap-[6px]" data-client-yes-no>
        <span className={cn(PILL, yes ? "bg-espresso text-on-dark" : "bg-card shadow-e1")}>
          Yes
        </span>
        <span className={cn(PILL, no ? "bg-espresso text-on-dark" : "bg-card shadow-e1")}>No</span>
      </div>
    );
  }
  if (q.type === "amount") {
    const values = (q.answer ?? {}) as Record<string, unknown>;
    return (
      <dl className="flex flex-col gap-[4px]" data-client-amounts>
        {(q.amountParts ?? []).map((part) => (
          <div key={part} className="flex justify-between text-[13px]">
            <dt>{part}</dt>
            <dd className="tabular-nums">{answerText(values[part])}</dd>
          </div>
        ))}
      </dl>
    );
  }
  if (q.type === "choice") {
    return (
      <div className="flex flex-wrap gap-[6px]" data-client-choices>
        {(q.choices ?? []).map((c) => (
          <span
            key={c}
            className={cn(PILL, q.answer === c ? "bg-espresso text-on-dark" : "bg-card shadow-e1")}
          >
            {c}
          </span>
        ))}
      </div>
    );
  }
  return <p className="text-[13px] text-ink-2">{answerText(q.answer)}</p>;
}

function Wording({ q }: { q: ClientQuestion }): JSX.Element {
  return (
    <p className="flex items-start gap-[6px] text-[13.5px] font-medium">
      <span className="flex-1">{q.wording}</span>
      {q.required && <span className="text-micro font-normal text-ink-3">Required</span>}
    </p>
  );
}

export function ClientQuestionPreview({
  question,
  followUps = [],
  className,
}: ClientQuestionPreviewProps): JSX.Element {
  return (
    <section
      data-client-question={question.key}
      className={cn(
        "flex flex-col gap-[10px] rounded-[12px] bg-card p-[12px] shadow-e1",
        className,
      )}
    >
      <Wording q={question} />
      <Body q={question} />
      {followUps.map((f) => (
        <div
          key={f.key}
          data-client-follow-up={f.key}
          className="flex flex-col gap-[6px] hairline-t pt-[8px]"
        >
          <Wording q={f} />
          {f.type === "upload_if_yes" ? (
            <span className="flex items-center gap-[8px]">
              <span className="text-[13px] font-medium text-espresso">Upload…</span>
              <span className={cn(PILL, "h-[24px] bg-card shadow-e1")}>Ignore</span>
            </span>
          ) : (
            <Body q={f} />
          )}
        </div>
      ))}
    </section>
  );
}
