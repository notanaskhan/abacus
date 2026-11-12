// T-04-T37 / TASK-7323 (SPEC-649 §6, AC-6.1 to AC-6.8): TAX-08 on a live build. The O2 drawer
// (420, peek, no scrim) over the return's workspace, on the routes T-04-T37 and P-10-T43 built:
//
// - Availability first: the workspace summary's `assistant` (`tax.assistant`'s reason for this
//   person). `consent_required` shows SPEC-649 AC-6.8's words and opens nothing, so no model is
//   called. Creating a session answers 409 `capability_unavailable` with `facts.reason` when
//   availability changed in between.
// - A new thread shows the three suggested prompts (TAX-08 b). The first ask creates the session
//   bound to the return (`POST /v1/workbench/sessions`, `subject_ref` tax_return:<id>) and posts
//   the message (`POST …/messages`, with an Idempotency-Key). History lists the person's threads on
//   this return (`GET /v1/workbench/sessions?subject_ref=…`).
// - The thread is the session snapshot (`GET /v1/workbench/sessions/{id}`). With `realtime.sse`
//   on, the tab's stream carries `session:<id>` (TASK-7325): each item written invalidates the
//   snapshot, beside the workspace's own topic. Without the stream it polls while a turn runs.
//   Agent text renders only through AgentBlocks and AgentText.
// - A plan opens its child run in the run pane (RunPane), where the person approves the plan.
//   The changes the child run proposes are listed under it (its writes, TASK-7325): a waiting one
//   offers "Approve adjustments…", which opens SHL-10's ApproveSheet in place (TAX-08's "→ SHL-10
//   confirmation"), where the person approves, edits or rejects; a decided one reads who decided.
//   Nothing here approves for the person, and no agent-owned control reads approve, send or sign.
import {
  agentRunWritesOptions,
  createSessionMutation,
  listSessionsOptions,
  postSessionMessageMutation,
  getSessionOptions,
  workspaceOptions,
} from "@abacus/api-client/query";
import type { SessionItemOut } from "@abacus/api-client";
import {
  AgentBlocks,
  type AgentBlocksPayload,
  AgentText,
  Button,
  Drawer,
  Skeleton,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { registerTopicKeys } from "../../app-core/realtime";
import { useRealtimeInterval, useRealtimeStream } from "../../app-core/realtime-hooks";
import { RunPane } from "../../domain/agents";
import { ApproveSheet } from "../SHL-10";
import { BLOCKER_COPY } from "../TAX-04/live-core";
import { COPY, IDLE_PROMPTS } from "./copy";

/** Polled while a turn runs, when the tab has no stream. */
export const TURN_POLL_MS = 1500;

// `session:<id>` refetches that session's snapshot (the generated key matches on `_id` and path).
registerTopicKeys("session", (topic) => [
  [{ _id: "getSession", path: { session_id: topic.slice("session:".length) } }],
]);

export const ASSISTANT_LIVE_COPY = {
  // SPEC-649 AC-6.8, verbatim.
  consent: "Agents are off for this taxpayer — §7216 consent isn't on file",
  // ADM-04's words for a firm-wide stop.
  agentsOff: "Paused for the whole firm",
  unavailable: COPY.notAllowed,
  openPlan: "Open plan",
  // TAX-08's ApprovalCard: "Approve adjustments" → SHL-10 confirmation.
  approveChanges: "Approve adjustments…",
  decided: (decision: string, by: string | null) =>
    `${decision === "approved" ? "✓ Approved" : decision === "rejected" ? "Rejected" : decision.replaceAll("_", " ")}${by === null ? "" : ` by ${by}`}`,
  back: "Back to the thread",
  noThreads: "No threads on this return yet.",
} as const;

function reasonWords(reason: string): string {
  if (reason === "consent_required" || reason === "consent_7216") {
    return ASSISTANT_LIVE_COPY.consent;
  }
  if (reason === "agents_off" || reason === "paused" || reason === "ai_policy_off") {
    return ASSISTANT_LIVE_COPY.agentsOff;
  }
  return ASSISTANT_LIVE_COPY.unavailable;
}

function newKey(): string {
  return globalThis.crypto.randomUUID();
}

interface ApiProblem {
  detail?: unknown;
  facts?: { reason?: unknown } | null;
}

function refusalReason(error: unknown): string {
  const e = (error ?? {}) as ApiProblem;
  return typeof e.facts?.reason === "string" ? e.facts.reason : "ai_unavailable";
}

function text(payload: Record<string, unknown>, key: string): string {
  const value = payload[key];
  return typeof value === "string" ? value : "";
}

function blocksOf(payload: Record<string, unknown>): AgentBlocksPayload | null {
  const blocks = payload.blocks as { parts?: unknown } | undefined;
  return blocks !== undefined && Array.isArray(blocks.parts)
    ? (blocks as AgentBlocksPayload)
    : null;
}

function Bubble({ body }: { body: string }): JSX.Element {
  return (
    <p
      data-actor="human"
      className="ml-auto max-w-[85%] whitespace-pre-line rounded-[12px] bg-card px-[12px] py-[8px] text-[13px] shadow-hair [overflow-wrap:anywhere]"
    >
      {body}
    </p>
  );
}

/** The child run's proposed changes under its plan (TASK-7325). */
function PlanChanges({ runId }: { runId: string }): JSX.Element | null {
  const queryClient = useQueryClient();
  const writes = useQuery(agentRunWritesOptions({ path: { run_id: runId } }));
  const [reviewing, setReviewing] = useState<string | null>(null);
  const proposals = (writes.data ?? []).filter(
    (w) => w.kind === "proposal" && w.proposal_id != null,
  );
  if (proposals.length === 0) return null;
  return (
    <ul aria-label={COPY.cardTitle} data-plan-changes className="flex flex-col gap-[6px]">
      {proposals.map((w) => (
        <li key={w.id} className="flex items-center justify-between gap-[8px] text-[12.5px]">
          <span>{COPY.cardTitle}</span>
          {w.decision == null && w.state === "waiting" ? (
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setReviewing(w.proposal_id ?? null);
              }}
            >
              {ASSISTANT_LIVE_COPY.approveChanges}
            </Button>
          ) : w.decision != null ? (
            <span className="text-ink-2">
              {ASSISTANT_LIVE_COPY.decided(w.decision, w.decided_by_name)}
            </span>
          ) : null}
        </li>
      ))}
      {reviewing !== null ? (
        <ApproveSheet
          proposalRef={reviewing}
          open
          onOpenChange={(next) => {
            if (next) return;
            setReviewing(null);
            void queryClient.invalidateQueries({ queryKey: [{ _id: "agentRunWrites" }] });
            void queryClient.invalidateQueries({ queryKey: [{ _id: "workspace" }] });
          }}
        />
      ) : null}
    </ul>
  );
}

function Item({
  item,
  onOpenPlan,
}: {
  item: SessionItemOut;
  onOpenPlan: (runId: string) => void;
}): JSX.Element | null {
  const payload = item.payload as Record<string, unknown>;
  switch (item.kind) {
    case "user_message":
    case "answer": {
      const blocked = text(payload, "blocked");
      return (
        <div data-item={item.kind} className="flex flex-col gap-[4px]">
          <Bubble body={text(payload, "body")} />
          {blocked !== "" ? (
            <p role="status" className="ml-auto text-[11.5px] text-ink-3">
              {reasonWords(blocked)}
            </p>
          ) : null}
        </div>
      );
    }
    case "agent_blocks": {
      const blocks = blocksOf(payload);
      return blocks === null ? null : (
        <div data-item="agent_blocks" className="rounded-[12px] bg-card p-[12px] shadow-e1">
          <AgentBlocks blocks={blocks} facts={{}} />
        </div>
      );
    }
    case "question": {
      const question = payload.question as { text?: unknown } | undefined;
      return (
        <div data-item="question" className="rounded-[12px] bg-card p-[12px] shadow-e1">
          <AgentText text={typeof question?.text === "string" ? question.text : ""} />
        </div>
      );
    }
    case "plan": {
      const steps = Array.isArray(payload.steps)
        ? (payload.steps as { key?: unknown; label?: unknown }[])
        : [];
      return (
        <div
          data-item="plan"
          className="flex flex-col gap-[6px] rounded-[12px] bg-card p-[12px] shadow-e1"
        >
          <ol className="flex list-decimal flex-col gap-[2px] pl-[18px] text-[12.5px]">
            {steps.map((s, i) => (
              <li key={typeof s.key === "string" ? s.key : String(i)}>
                <AgentText inline text={typeof s.label === "string" ? s.label : ""} />
              </li>
            ))}
          </ol>
          {item.run_id ? <PlanChanges runId={item.run_id} /> : null}
          {item.run_id ? (
            <Button
              variant="secondary"
              size="sm"
              className="self-start"
              onClick={() => {
                if (item.run_id) onOpenPlan(item.run_id);
              }}
            >
              {ASSISTANT_LIVE_COPY.openPlan}
            </Button>
          ) : null}
        </div>
      );
    }
    case "notice":
      return (
        <p data-item="notice" role="status" className="text-[12px] text-ink-3">
          {BLOCKER_COPY.generic}
        </p>
      );
    default:
      return null;
  }
}

export interface AssistantLiveProps {
  returnId: string;
  open: boolean;
  onClose: () => void;
  /** The run pane's trace link (the host's route). */
  onTrace?: (runId: string) => void;
}

export function AssistantLive({
  returnId,
  open,
  onClose,
  onTrace,
}: AssistantLiveProps): JSX.Element {
  const queryClient = useQueryClient();
  const subjectRef = `tax_return:${returnId}`;
  const summary = useQuery(workspaceOptions({ path: { return_id: returnId } }));
  const word = summary.data?.assistant;
  const available = word === "available";
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [view, setView] = useState<"thread" | "history">("thread");
  const [planRun, setPlanRun] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [refused, setRefused] = useState<string | null>(null);
  const history = useQuery({
    ...listSessionsOptions({ query: { subject_ref: subjectRef } }),
    enabled: open && available && view === "history",
  });
  useRealtimeStream(open && sessionId !== null ? [`session:${sessionId}`] : []);
  const streaming = useRealtimeInterval("record") === false;
  const snapshot = useQuery({
    ...getSessionOptions({ path: { session_id: sessionId ?? "" } }),
    enabled: open && sessionId !== null,
    refetchInterval: (q) =>
      !streaming && q.state.data?.state === "running" ? TURN_POLL_MS : false,
  });
  const create = useMutation(createSessionMutation());
  const post = useMutation({
    ...postSessionMessageMutation(),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: [{ _id: "getSession" }] });
    },
  });
  const items = snapshot.data?.items ?? [];
  const running = snapshot.data?.state === "running";
  const canMessage = sessionId === null || snapshot.data?.allowed_actions.includes("message");
  // An open question is answered by the next message (answers_seq), until its answer arrives.
  const openQuestion = [...items]
    .reverse()
    .find(
      (q) =>
        q.kind === "question" &&
        !items.some(
          (a) =>
            a.kind === "answer" && (a.payload as Record<string, unknown>).answers_seq === q.seq,
        ),
    );

  const ask = async (body: string): Promise<void> => {
    const trimmed = body.trim();
    if (trimmed === "" || !available) return;
    setRefused(null);
    let id = sessionId;
    try {
      if (id === null) {
        const made = await create.mutateAsync({
          body: { subject_ref: { kind: "tax_return", id: returnId } },
        });
        id = made.id;
        setSessionId(id);
      }
      await post.mutateAsync({
        path: { session_id: id },
        headers: { "Idempotency-Key": newKey() },
        body: {
          body: trimmed,
          ...(openQuestion === undefined ? {} : { answers_seq: openQuestion.seq }),
        },
      });
      setDraft("");
    } catch (error) {
      setRefused(refusalReason(error));
    }
  };

  const body = (): JSX.Element => {
    if (summary.isPending) {
      return <Skeleton aria-label={COPY.loading} className="m-[12px] h-[120px]" />;
    }
    if (!available) {
      return (
        <p data-assistant="off" role="status" className="p-[12px] text-[13px] text-ink-2">
          {reasonWords(word ?? "ai_unavailable")}
        </p>
      );
    }
    if (planRun !== null) {
      return (
        <div className="flex min-h-0 flex-1 flex-col">
          <Button
            variant="ghost"
            size="sm"
            className="self-start"
            onClick={() => {
              setPlanRun(null);
            }}
          >
            {ASSISTANT_LIVE_COPY.back}
          </Button>
          <RunPane runId={planRun} onTrace={onTrace ?? (() => undefined)} />
        </div>
      );
    }
    if (view === "history") {
      const threads = history.data?.items ?? [];
      return (
        <ul aria-label={COPY.history} data-assistant="history" className="flex flex-col p-[8px]">
          {history.isPending ? (
            <Skeleton className="h-[44px]" />
          ) : threads.length === 0 ? (
            <li className="p-[8px] text-[12.5px] text-ink-3">{ASSISTANT_LIVE_COPY.noThreads}</li>
          ) : (
            threads.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  className="flex h-[44px] w-full items-center rounded-[6px] px-[8px] text-left text-[13px] hover:bg-hover"
                  onClick={() => {
                    setSessionId(t.id);
                    setView("thread");
                  }}
                >
                  {t.title}
                </button>
              </li>
            ))
          )}
        </ul>
      );
    }
    return (
      <div data-assistant="thread" className="flex flex-col gap-[10px] p-[12px]">
        {sessionId === null ? (
          <ul aria-label="Suggested prompts" className="flex flex-col gap-[8px]">
            {IDLE_PROMPTS.map((p) => (
              <li key={p}>
                <button
                  type="button"
                  disabled={create.isPending || post.isPending}
                  className="w-full rounded-[12px] bg-card p-[12px] text-left text-[12.5px] shadow-e1"
                  onClick={() => void ask(p)}
                >
                  {p}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          items.map((item) => <Item key={item.id} item={item} onOpenPlan={setPlanRun} />)
        )}
        {running ? <Skeleton aria-label={COPY.loading} className="h-[48px]" /> : null}
        {refused !== null ? (
          <p role="alert" className="text-[12.5px] text-red-ink">
            {reasonWords(refused)}
          </p>
        ) : null}
      </div>
    );
  };

  return (
    <Drawer
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={COPY.title}
      width={420}
      peek
      meta={
        available ? (
          <span className="flex gap-[6px]">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setPlanRun(null);
                setView(view === "history" ? "thread" : "history");
              }}
            >
              {COPY.history}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setPlanRun(null);
                setSessionId(null);
                setView("thread");
              }}
            >
              {COPY.newThread}
            </Button>
          </span>
        ) : undefined
      }
      footer={
        available && view === "thread" && planRun === null ? (
          <form
            className="flex items-end gap-[6px]"
            onSubmit={(e) => {
              e.preventDefault();
              void ask(draft);
            }}
          >
            <textarea
              aria-label={COPY.composer}
              placeholder={COPY.composer}
              value={draft}
              maxLength={8000}
              rows={2}
              onChange={(e) => {
                setDraft(e.target.value);
              }}
              className="min-h-[44px] flex-1 resize-none rounded-[10px] bg-card px-[10px] py-[8px] text-[13px] shadow-hair"
            />
            <Button
              type="submit"
              variant="primary"
              disabled={
                draft.trim() === "" || running || create.isPending || post.isPending || !canMessage
              }
            >
              {COPY.send}
            </Button>
          </form>
        ) : undefined
      }
      bare
    >
      {body()}
    </Drawer>
  );
}
