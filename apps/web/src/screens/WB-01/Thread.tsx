// WB-01's thread (W-02-T17; docs/screens/WB-01.md states a–e and g; W-02 §3.4–§3.7): the selected
// session's items on the kit's ChatThread, bound to the session's snapshot and its realtime topic
// (the E6 RunStore's SSE source refreshes it): the discovery block's InlineTable (AgentBlocks),
// the open question as QuestionCard steps above the composer (Skip, Previous, Next; an answer is
// the person's turn naming the question), the plan and run items with "View run", a failed step's
// ChatErrorRow with Retry (the run's own step retry) and View run, the code's notices
// (`nothing_written`, `plans_off`, `today_read_only`) in fixed words, and the person's bubble menu
// (Copy, Edit and resend). A locked session draws nothing (INV-3); the composer is the owner's.
import type { SessionItemOut, SessionSnapshotOut } from "@abacus/api-client";
import { retryStepMutation } from "@abacus/api-client/query";
import {
  ChatThread,
  type QuestionAnswer,
  QuestionCard,
  type QuestionPayload,
  type ThreadItem,
} from "@abacus/ui";
import { useMutation } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { usePostMessage } from "../../domain/workbench";
import { COPY } from "./copy";

/** The code's notices in fixed words (never model text). */
export const NOTICE_WORDS: Readonly<Record<string, string>> = {
  nothing_written: COPY.nothingWritten,
  plans_off: COPY.plansOff,
  today_read_only: COPY.todayReadOnly,
  capability_unavailable: COPY.unavailable,
  turn_failed: COPY.turnFailed,
};

/** Items as the thread reads them: notices carry their words; context and drill rows are WB-02's
 * and WB-03's, so they are left out here. */
export function threadItems(items: readonly SessionItemOut[]): ThreadItem[] {
  return items
    .filter((i) => !["context_added", "context_removed", "drill"].includes(i.kind))
    .map((i) =>
      i.kind === "notice"
        ? {
            ...i,
            payload: {
              ...i.payload,
              text: NOTICE_WORDS[String(i.payload["code"] ?? "")] ?? COPY.turnFailed,
            },
          }
        : (i as ThreadItem),
    );
}

/** The newest question no later answer names (AC-Q4: other messages leave it open). */
export function openQuestion(items: readonly SessionItemOut[]): SessionItemOut | null {
  const answered = new Set(
    items.filter((i) => i.kind === "answer").map((i) => Number(i.payload["answers_seq"])),
  );
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i];
    if (item?.kind === "question" && !answered.has(item.seq)) return item;
  }
  return null;
}

export function questionOf(item: SessionItemOut): QuestionPayload | null {
  // The turn's item nests it (`{v, turn_of, question}`); a recorded thread may carry it flat.
  const q = (item.payload["question"] ?? item.payload) as Partial<QuestionPayload> | undefined;
  if (q === undefined || !Array.isArray(q.steps) || q.steps.length === 0) return null;
  return { question_id: q.question_id ?? item.id, ...q, steps: q.steps } as QuestionPayload;
}

export function Thread({
  snapshot,
  sessionId,
  onOpenRun,
}: {
  snapshot: SessionSnapshotOut | undefined;
  sessionId: string;
  onOpenRun: (runId: string) => void;
}): JSX.Element {
  const post = usePostMessage();
  const retry = useMutation(retryStepMutation());
  const [editing, setEditing] = useState<{ seq: number; nonce: number; text: string } | null>(null);
  const items = snapshot?.items ?? [];
  const asked = openQuestion(items);
  const question = asked === null ? null : questionOf(asked);
  const owner = snapshot?.allowed_actions.includes("message") === true;
  const answer = (a: QuestionAnswer) => {
    if (asked === null || question === null) return;
    const text =
      "skipped" in a
        ? (question.skipText ?? COPY.skip)
        : (question.steps[a.step - 1]?.options.find((o) => o.key === a.key)?.title ?? a.key);
    void post.post(sessionId, text, { answersSeq: asked.seq });
  };
  return (
    <ChatThread
      items={threadItems(items)}
      locked={snapshot?.locked === true}
      {...(question !== null && owner
        ? { above: <QuestionCard question={question} onAnswer={answer} busy={post.isPending} /> }
        : {})}
      {...(editing === null ? {} : { draft: { text: editing.text, nonce: editing.nonce } })}
      slots={{
        plan: (item) => (
          <div data-row="plan" className="rounded-[12px] bg-card p-[12px] text-[13px] shadow-e1">
            <p className="font-medium text-ink">{COPY.planReady}</p>
            {item.run_id ? (
              <button
                type="button"
                onClick={() => {
                  onOpenRun(item.run_id ?? "");
                }}
                className="mt-[4px] text-[12.5px] text-ink-2 hover:underline"
              >
                {COPY.viewRun}
              </button>
            ) : null}
          </div>
        ),
        question: () => null, // the open one is above the composer; answered ones read as turns
      }}
      onOpenRun={onOpenRun}
      onRetryStep={(stepId) => {
        const runId = items.find((i) => i.step_id === stepId)?.run_id;
        if (!runId) return;
        retry.mutate({
          path: { run_id: runId, step_id: stepId },
          headers: { "Idempotency-Key": crypto.randomUUID() },
        });
      }}
      {...(owner
        ? {
            onSend: (body: string) => {
              void post.post(
                sessionId,
                body,
                editing === null ? {} : { editsSeq: editing.seq },
              );
              setEditing(null);
            },
            onEditResend: (seq: number, text: string) => {
              setEditing({ seq, text, nonce: Date.now() });
            },
          }
        : {})}
    />
  );
}
