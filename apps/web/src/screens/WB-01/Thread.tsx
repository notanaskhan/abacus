// WB-01's thread (W-02-T17; docs/screens/WB-01.md states a–e and g; W-02 §3.4–§3.7): the selected
// session's items on the kit's ChatThread, bound to the session's snapshot and its realtime topic
// (the E6 RunStore's SSE source refreshes it): the discovery block's InlineTable (AgentBlocks),
// the open question as QuestionCard steps above the composer (Skip, Previous, Next; an answer is
// the person's turn naming the question), the plan and run items with "View run", a failed step's
// ChatErrorRow with Retry (the run's own step retry) and View run, the code's notices
// (`nothing_written`, `plans_off`, `today_read_only`) in fixed words, and the person's bubble menu
// (Copy, Edit and resend). A locked session draws nothing (INV-3); the composer is the owner's.
import type { SessionItemOut, SessionSnapshotOut } from "@abacus/api-client";
import {
  listCapabilitiesOptions,
  proposalApproveMutation,
  proposalUndoMutation,
  retryStepMutation,
} from "@abacus/api-client/query";
import {
  ChatThread,
  type QuestionAnswer,
  QuestionCard,
  type QuestionPayload,
  type ThreadItem,
} from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { nowMs } from "../../app-core/clock";
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
              text: NOTICE_WORDS[typeof i.payload["code"] === "string" ? i.payload["code"] : ""] ?? COPY.turnFailed,
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
  return { question_id: q.question_id ?? item.id, ...q, steps: q.steps };
}

/** W-02-T22 (DF-04): the assistant's availability in words, and whether consent can be asked. */
export const UNAVAILABLE_WORDS: Readonly<Record<string, string>> = {
  ai_excluded: COPY.unavailable,
  ai_policy_off: COPY.unavailable,
  paused: COPY.paused,
  consent_7216: COPY.consentOff,
  not_on_team: COPY.notOnTeam,
  capability_unavailable: COPY.unavailable,
};

export function availabilityOf(
  caps: { items?: readonly { capability: string; available: boolean; reason?: string | null }[] } | undefined,
  capability = "workbench.assistant",
): { reason: string | null; consent: boolean } {
  const hit = caps?.items?.find((c) => c.capability === capability);
  if (caps === undefined) return { reason: null, consent: false };
  if (hit === undefined) return { reason: COPY.unavailable, consent: false };
  if (hit.available) return { reason: null, consent: false };
  const code = hit.reason ?? "capability_unavailable";
  return { reason: UNAVAILABLE_WORDS[code] ?? COPY.unavailable, consent: code === "consent_7216" };
}

export function Thread({
  snapshot,
  sessionId,
  onOpenRun,
  onRequestConsent,
  planSlot,
  onOpenArtifact,
}: {
  snapshot: SessionSnapshotOut | undefined;
  sessionId: string;
  onOpenRun: (runId: string) => void;
  /** W-02-T22: "Request consent" for a permitted role (C19's consent request, a person's act). */
  onRequestConsent?: () => void;
  /** W-02-T21: WB-03 draws the plan item as its PlanCard on the run's plan read. */
  planSlot?: (item: ThreadItem) => ReactNode;
  /** W-02-T21: Open on an artifact (the O4 preview overlay). */
  onOpenArtifact?: (artifactId: string) => void;
}): JSX.Element {
  const post = usePostMessage();
  const caps = useQuery({ ...listCapabilitiesOptions(), retry: false });
  // W-02-T21 (WB-03 d, e): Save to Files is the owner's approval of the run's save proposal; the
  // approved line offers Undo for 10 seconds (DEC-24), then the file is filed by the run.
  const approveSave = useMutation(proposalApproveMutation());
  const undoSave = useMutation(proposalUndoMutation());
  const [approved, setApproved] = useState<{ proposal: string; decision: string } | null>(null);
  const available = availabilityOf(caps.data);
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
  const undoLine =
    approved === null ? null : (
      <p data-approved-line className="flex items-center gap-[8px] text-[12.5px] text-ink-2">
        <span className="flex-1">{COPY.savedApproved}</span>
        <button
          type="button"
          onClick={() => {
            void undoSave.mutateAsync({
              path: { proposal_id: approved.proposal },
              body: { decision_id: approved.decision },
              headers: { "Idempotency-Key": crypto.randomUUID() },
            });
            setApproved(null);
          }}
          className="text-ink hover:underline"
        >
          {COPY.undo}
        </button>
      </p>
    );
  const questionCard =
    question !== null && owner ? (
      <QuestionCard question={question} onAnswer={answer} busy={post.isPending} />
    ) : null;
  return (
    <ChatThread
      items={threadItems(items)}
      locked={snapshot?.locked === true}
      {...(questionCard !== null || undoLine !== null
        ? { above: <>{undoLine}{questionCard}</> }
        : {})}
      {...(editing === null ? {} : { draft: { text: editing.text, nonce: editing.nonce } })}
      {...(available.reason === null ? {} : { composerDisabledReason: available.reason })}
      {...(available.consent && onRequestConsent !== undefined
        ? {
            composerAction: (
              <button type="button" onClick={onRequestConsent} className="text-ink hover:underline">
                {COPY.requestConsent}
              </button>
            ),
          }
        : {})}
      slots={{
        plan: planSlot ?? ((item) => (
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
        )),
        question: () => null, // the open one is above the composer; answered ones read as turns
      }}
      onOpenRun={onOpenRun}
      onArtifact={(artifactId, intent) => {
        const row = items.find((i) => i.kind === "artifact" && i.payload["artifact_id"] === artifactId);
        if (intent === "open") {
          onOpenArtifact?.(artifactId);
          return;
        }
        if (intent === "download") {
          window.location.assign(`/v1/run-artifacts/${artifactId}/download`);
          return;
        }
        const proposal = row?.payload["proposal_id"];
        if (!owner || typeof proposal !== "string") return;
        void approveSave
          .mutateAsync({
            path: { proposal_id: proposal },
            body: { seen_version: Number(row?.payload["proposal_version"] ?? 1) },
            headers: { "Idempotency-Key": crypto.randomUUID() },
          })
          .then((p) => {
            const decision = p.decision?.id;
            if (decision === undefined) return;
            setApproved({ proposal, decision });
            window.setTimeout(() => {
              setApproved(null);
            }, 10_000);
          });
      }}
      onRetryStep={(stepId) => {
        const row = items.find((i) => i.step_id === stepId);
        const runId = row?.run_id;
        if (!runId) return;
        // W-02-T21 (AC-G4): a step with a failure ledger re-reads only those items.
        const failed = Number(row.payload["failed"] ?? 0);
        retry.mutate({
          path: { run_id: runId, step_id: stepId },
          ...(failed > 0 ? { body: { scope: "failed_items" as const } } : {}),
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
              setEditing({ seq, text, nonce: nowMs() });
            },
          }
        : {})}
    />
  );
}
