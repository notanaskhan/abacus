import type {
  AgentRunOut,
  RunItemOut,
  RunProjectionLevelOut,
  RunViewOut,
} from "@abacus/api-client";
import {
  agentRunOptions,
  answerQuestionMutation,
  approveRunPlanMutation,
  createFeedbackMutation,
  redirectRunMutation,
  retryStepMutation,
  signOffRunMutation,
  skipQuestionMutation,
  startEngagementRunMutation,
} from "@abacus/api-client/query";
import {
  AgentBlocks,
  Button,
  count,
  Icon,
  type IconName,
  ProgressBar,
  Skeleton,
  ConfirmDialog,
  StatusPill,
  toast,
  useNow,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, type JSX, useContext, useState } from "react";
import { useFlag } from "../../app-core/flags";
import { narrate } from "./narrate";
import { isActive, POLL_MS, useRunFeed } from "./runFeed";

// P-09-T14 (DEC-3134): every human action binds to P-10's C6 v2 routes and renders only when the
// server lists its matrix action on the run (`allowed_actions`) and `agent_runtime.v2` is on (the
// routes answer 404 while it is off). Nothing is optimistic: a control waits for the server, a
// refusal shows the server's reason, and the run view and feed are read again after each act. An
// agent context is never listed any of these actions, so it is offered none.
interface RunActs {
  can: (action: string) => boolean;
  /** The server's refusal, in its words (the error code, or its detail). */
  refused: (error: unknown) => void;
  done: () => void;
}

const NO_ACTS: RunActs = { can: () => false, refused: () => undefined, done: () => undefined };
const ActsContext = createContext<RunActs>(NO_ACTS);

export function refusalWords(error: unknown): string {
  if (typeof error === "object" && error !== null) {
    const body = error as { code?: unknown; detail?: unknown };
    if (typeof body.code === "string") return body.code.replaceAll("_", " ");
    if (typeof body.detail === "string") return body.detail;
  }
  return "The run did not take that action.";
}

function key(): { "Idempotency-Key": string } {
  return { "Idempotency-Key": crypto.randomUUID() };
}

// SHL-13 run pane (P-09-T09; SPEC-648 Story 1.1 to 1.3; handoff SHL-13 frames 1 to 8): one run in
// the 330 dock: the header with the live dot and "Sign off run", the run projection by level
// (code's counts from C6 v1.1's `levels`), and the thread in the C6 v2 wire set: the person's
// bubbles, narration through AgentBlocks, tool cards in their six states, the level row, the
// decision and ask cards, failures and the close run card. The composer and every human action
// ("Sign off run", plan and question answers, Retry) are bound to P-10's run commands (P-09-T14).
// Nothing here decides for a person (ADR-005; frontend rule 3).

/** The engagement run's five levels (SHL-13 projection strip). */
export const LEVEL_LABEL: Readonly<Record<number, string>> = {
  1: "Foundation",
  2: "Planning",
  3: "Sampling",
  4: "Testing",
  5: "Completion",
};

/** A tool card's step state as §3.3.1 words it, with its disc and pill. */
export type ToolState =
  "dispatched" | "running" | "waiting_on_inputs" | "blocked" | "succeeded" | "failed";

export const TOOL_STATE: Readonly<
  Record<ToolState, { label: string; tone: "neutral" | null; disc: string }>
> = {
  dispatched: { label: "Dispatched", tone: "neutral", disc: "todo" },
  running: { label: "Running", tone: null, disc: "run" },
  waiting_on_inputs: { label: "Waiting on inputs", tone: "neutral", disc: "half" },
  blocked: { label: "Blocked on a partner decision", tone: null, disc: "warn" },
  succeeded: { label: "Complete", tone: null, disc: "done" },
  failed: { label: "Failed", tone: null, disc: "fail" },
};

function toolState(outcome: string | null): ToolState {
  return outcome !== null && outcome in TOOL_STATE ? (outcome as ToolState) : "dispatched";
}

const TERMINAL = new Set(["succeeded", "failed"]);

/** "Run projection · 14 workpapers · 5 levels". */
export function projectionTitle(levels: readonly RunProjectionLevelOut[]): string {
  const total = levels.reduce((n, lv) => n + lv.total, 0);
  return `Run projection · ${count(total)} workpapers · ${count(levels.length)} levels`;
}

/** The ink-3 tail of a level row: "1 blocked · 1 running" (and failures). */
export function levelTail(level: RunProjectionLevelOut): string | null {
  const parts: string[] = [];
  const { blocked = 0, running = 0, failed = 0 } = level;
  if (blocked > 0) parts.push(`${count(blocked)} blocked`);
  if (running > 0) parts.push(`${count(running)} running`);
  if (failed > 0) parts.push(`${count(failed)} failed`);
  return parts.length === 0 ? null : parts.join(" · ");
}

function StatusDisc({ disc }: { disc: string }): JSX.Element {
  // The six discs of SHL-13: ring, spinner, half disc, warning, check, cross.
  const icon: IconName =
    disc === "done"
      ? "circle-check"
      : disc === "fail"
        ? "circle-x"
        : disc === "warn"
          ? "triangle-alert"
          : disc === "run"
            ? "circle-dashed"
            : disc === "half"
              ? "circle-dot"
              : "circle";
  return (
    <span
      data-disc={disc}
      aria-hidden="true"
      className={
        disc === "done"
          ? "text-green"
          : disc === "fail"
            ? "text-red"
            : disc === "warn"
              ? "text-amber"
              : "text-ink-2"
      }
    >
      <Icon
        name={icon}
        size={15}
        {...(disc === "run" ? { className: "motion-safe:animate-spin" } : {})}
      />
    </span>
  );
}

function ProjectionStrip({
  levels,
  planReady = false,
}: {
  levels: readonly RunProjectionLevelOut[];
  planReady?: boolean;
}): JSX.Element {
  const [open, setOpen] = useState(true);
  return (
    <section
      aria-label="Run projection"
      className="mx-[10px] rounded-[10px] border-[0.5px] border-hair bg-shell px-[10px] py-[8px]"
    >
      <button
        type="button"
        aria-expanded={open}
        className="flex w-full items-center justify-between text-[11.5px] font-medium text-ink-2"
        onClick={() => {
          setOpen(!open);
        }}
      >
        {projectionTitle(levels)}
        <span className="flex items-center gap-1">
          {planReady && (
            <span
              data-plan-ready="true"
              className="rounded-full bg-amber-tint px-[6px] text-amber-ink"
            >
              Plan ready — approve?
            </span>
          )}
          <Icon name="chevron-down" size={12} />
        </span>
      </button>
      {open && (
        <ul className="pt-[4px]">
          {levels.map((lv) => {
            const complete = lv.total > 0 && lv.done === lv.total;
            const tail = levelTail(lv);
            return (
              <li
                key={lv.level}
                data-level={lv.level}
                className="flex h-[22px] items-center gap-2 text-dense"
              >
                <span className="min-w-0 flex-1">
                  {LEVEL_LABEL[lv.level] ?? `Level ${count(lv.level)}`}
                </span>
                {tail !== null && <span className="text-[11px] text-ink-3">{tail}</span>}
                <span
                  className={
                    complete
                      ? "rounded-full bg-green-tint px-[6px] text-green-ink tabular-nums"
                      : "rounded-full bg-chip px-[6px] tabular-nums"
                  }
                >
                  {complete
                    ? `${count(lv.done ?? 0)} of ${count(lv.total)} ✓`
                    : `${count(lv.done ?? 0)} of ${count(lv.total)}`}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function Blocks({ item }: { item: RunItemOut }): JSX.Element | null {
  if (item.blocks == null) return null;
  return <AgentBlocks blocks={item.blocks} facts={{}} />;
}

/** SHL-13 revision 4: the thumbs-down reasons, in the handoff's words, and C6 v2's codes for them
 * (DEC-3023: the contract's words differ; the screen keeps the handoff's). */
export const FEEDBACK_REASONS = [
  ["Wrong period", "wrong_figure"],
  ["Wrong document", "wrong_source"],
  ["Missed evidence", "missed_something"],
  ["Wording", "not_useful"],
  ["Other", "other"],
] as const;
type FeedbackReason = (typeof FEEDBACK_REASONS)[number][1];

/** A finished card's footer: Rerun and Follow up (a person's, bound in P-09-T14), and the thumbs
 * that store a correction. Thumbs-down needs a reason before Submit. */
function FeedbackFooter({ runId, item }: { runId: string; item: RunItemOut }): JSX.Element | null {
  const acts = useContext(ActsContext);
  const [picking, setPicking] = useState(false);
  const [reason, setReason] = useState<FeedbackReason | null>(null);
  const [sent, setSent] = useState<"up" | "down" | null>(null);
  const send = useMutation({
    ...createFeedbackMutation(),
    onSuccess: (_out, vars) => {
      setSent(vars.body.rating);
      setPicking(false);
    },
    onError: acts.refused,
  });
  if (!acts.can("agent_feedback.create")) return null;
  const rate = (rating: "up" | "down", why: FeedbackReason | null): void => {
    send.mutate({
      body: { run_id: runId, rating, reason: why, item_id: item.ref_id ?? null },
      headers: { "Idempotency-Key": crypto.randomUUID() },
    });
  };
  return (
    <div data-tool-footer="true" className="relative flex items-center gap-1 pt-[6px]">
      <span className="flex-1" />
      <button
        type="button"
        aria-label="Helpful"
        aria-pressed={sent === "up"}
        disabled={sent !== null || send.isPending}
        className="text-ink-3"
        onClick={() => {
          rate("up", null);
        }}
      >
        <Icon name="thumbs-up" size={13} />
      </button>
      <button
        type="button"
        aria-label="Not helpful"
        aria-expanded={picking}
        aria-pressed={sent === "down"}
        disabled={sent !== null || send.isPending}
        className="text-ink-3"
        onClick={() => {
          setPicking(!picking);
        }}
      >
        <Icon name="thumbs-down" size={13} />
      </button>
      {picking && (
        <div
          role="dialog"
          aria-label="What was wrong"
          className="absolute right-0 top-[30px] z-10 w-[220px] rounded-[10px] bg-card p-[8px] shadow-e2"
        >
          <ul className="flex flex-col">
            {FEEDBACK_REASONS.map(([label, code]) => (
              <li key={code}>
                <label className="flex h-[28px] items-center gap-2 text-[12px]">
                  <input
                    type="radio"
                    name={`reason-${String(item.seq)}`}
                    checked={reason === code}
                    onChange={() => {
                      setReason(code);
                    }}
                  />
                  {label}
                </label>
              </li>
            ))}
          </ul>
          <div className="flex justify-end pt-[4px]">
            <Button
              size="xs"
              disabled={reason === null || send.isPending}
              onClick={() => {
                rate("down", reason);
              }}
            >
              Submit
            </Button>
          </div>
          {send.isError && (
            <p className="pt-[4px] text-[11px] text-ink-3">
              Feedback isn&apos;t on for this firm yet.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function ToolCard({
  runId,
  item,
  selected,
  onSelect,
  onTrace,
}: {
  runId: string;
  item: RunItemOut;
  selected: boolean;
  onSelect?: ((ref: string) => void) | undefined;
  onTrace: () => void;
}): JSX.Element {
  const state = toolState(item.outcome);
  const look = TOOL_STATE[state];
  const acts = useContext(ActsContext);
  const retry = useMutation({
    ...retryStepMutation(),
    onSuccess: acts.done,
    onError: acts.refused,
  });
  const [open, setOpen] = useState(false);
  // Waiting, blocked and failed cards show their body (needs line, error); a finished one on click.
  const body = state === "succeeded" ? open : item.blocks != null;
  return (
    <li
      data-tool-card={state}
      data-selected={selected ? "true" : undefined}
      className="rounded-[10px] bg-card px-[11px] pb-[9px] pt-[8px] shadow-e1"
    >
      <button
        type="button"
        aria-expanded={state === "succeeded" ? open : undefined}
        className="flex w-full items-center gap-2 text-left"
        onClick={() => {
          setOpen(!open);
          if (item.ref_id !== null && onSelect !== undefined) onSelect(item.ref_id);
        }}
      >
        <StatusDisc disc={look.disc} />
        <span className="flex-1 text-[12px] font-medium">Execute</span>
        {state === "blocked" ? (
          <span className="text-[11.5px] text-amber-ink">{look.label}</span>
        ) : state === "failed" ? (
          <span className="text-[11.5px] font-medium text-red-ink">{look.label}</span>
        ) : state === "running" ? (
          <span className="text-[11.5px] text-ink-3">{look.label}</span>
        ) : look.tone !== null ? (
          <StatusPill tone={look.tone}>{look.label}</StatusPill>
        ) : null}
      </button>
      <p className="flex items-center gap-1 pt-[2px] text-[12px] text-ink-2">
        <Icon name="chevron-right" size={12} />
        <span className="min-w-0 truncate">{item.detail ?? item.code.replaceAll("_", " ")}</span>
      </p>
      {body && (
        <div className="pt-[6px] text-[11.5px]">
          <Blocks item={item} />
        </div>
      )}
      {(state === "succeeded" ? open : state === "failed") && (
        <div className="flex justify-end gap-2 pt-[6px]">
          {state === "failed" && item.ref_id !== null && acts.can("agent_run.control") && (
            <Button
              size="xs"
              variant="secondary"
              disabled={retry.isPending}
              onClick={() => {
                if (item.ref_id !== null)
                  retry.mutate({ path: { run_id: runId, step_id: item.ref_id }, headers: key() });
              }}
            >
              Retry
            </Button>
          )}
          <Button size="xs" variant="ghost" onClick={onTrace}>
            Open trace
          </Button>
        </div>
      )}
      {state === "succeeded" && open && <FeedbackFooter runId={runId} item={item} />}
    </li>
  );
}

/** SHL-13 frame 8: a close run's task row (✓ done, spinner running), no tool-card chrome. */
function TaskRow({ item }: { item: RunItemOut }): JSX.Element {
  const state = toolState(item.outcome);
  return (
    <li data-task-row={state} className="flex h-[40px] items-center gap-2 text-[12.5px]">
      <StatusDisc disc={TOOL_STATE[state].disc} />
      <span className="min-w-0 flex-1 truncate">{item.detail ?? item.code}</span>
    </li>
  );
}

/** The question's options in the order the blocks number them (their `key`s). */
function optionKeys(item: RunItemOut): string[] {
  const parts = (item.blocks?.parts ?? []) as readonly { kind?: string; options?: unknown }[];
  return parts.flatMap((p) =>
    p.kind === "options" && Array.isArray(p.options)
      ? (p.options as readonly { key?: unknown }[]).flatMap((o) =>
          typeof o.key === "string" ? [o.key] : [],
        )
      : [],
  );
}

/** SHL-13 frame 5: the question card. Typing answers it (Enter), Esc skips it; the digits 1-9
 * pick an option the blocks number. Each act waits for the server. */
function QuestionCard({ runId, item }: { runId: string; item: RunItemOut }): JSX.Element {
  const acts = useContext(ActsContext);
  const [text, setText] = useState("");
  const answer = useMutation({
    ...answerQuestionMutation(),
    onSuccess: acts.done,
    onError: acts.refused,
  });
  const skip = useMutation({
    ...skipQuestionMutation(),
    onSuccess: acts.done,
    onError: acts.refused,
  });
  const questionId = item.ref_id;
  const can = questionId !== null && acts.can("agent_run.answer");
  const busy = answer.isPending || skip.isPending;
  const send = (body: { option_key?: string | null; text?: string | null }): void => {
    if (questionId === null) return;
    answer.mutate({ path: { run_id: runId, question_id: questionId }, body, headers: key() });
  };
  const doSkip = (): void => {
    if (questionId === null) return;
    skip.mutate({ path: { run_id: runId, question_id: questionId }, headers: key() });
  };
  return (
    <li
      data-ask-card="question"
      className="rounded-[10px] bg-card px-[12px] py-[10px] text-[12.5px] shadow-ask"
      onKeyDown={(e) => {
        if (!can || busy) return;
        if (e.key === "Escape") {
          e.preventDefault();
          doSkip();
        } else if (/^[1-9]$/.test(e.key) && e.target === e.currentTarget) {
          const picked = optionKeys(item)[Number(e.key) - 1];
          if (picked === undefined) return;
          e.preventDefault();
          send({ option_key: picked });
        }
      }}
    >
      <p className="flex items-center gap-2 pb-[6px]">
        <span className="flex size-[18px] items-center justify-center rounded-full bg-chip text-[11px] font-medium">
          ?
        </span>
        <span className="flex-1 font-medium">{item.detail ?? ""}</span>
        <span className="text-[11px] text-ink-3">1 of 1</span>
      </p>
      <Blocks item={item} />
      {can && (
        <form
          className="flex items-center gap-2 pt-[8px]"
          onSubmit={(e) => {
            e.preventDefault();
            if (text.trim() !== "") send({ text: text.trim() });
          }}
        >
          <input
            aria-label="Answer"
            value={text}
            disabled={busy}
            onChange={(e) => {
              setText(e.target.value);
            }}
            className="h-[28px] min-w-0 flex-1 rounded-[8px] bg-nested px-[8px] text-[12.5px]"
          />
          <Button size="xs" variant="ghost" type="button" disabled={busy} onClick={doSkip}>
            Skip
          </Button>
          <Button size="xs" type="submit" disabled={busy || text.trim() === ""}>
            Next
          </Button>
        </form>
      )}
    </li>
  );
}

function ThreadItem({
  runId,
  item,
  selectedRef,
  onSelectRef,
  onTrace,
  onOpenDecision,
}: {
  runId: string;
  item: RunItemOut;
  selectedRef?: string | null | undefined;
  onSelectRef?: ((ref: string) => void) | undefined;
  onTrace: () => void;
  onOpenDecision?: ((ref: string) => void) | undefined;
}): JSX.Element {
  const kind = item.session_kind ?? "notice";
  const acts = useContext(ActsContext);
  switch (kind) {
    case "user":
      return (
        <li className="ml-auto max-w-[85%] rounded-[14px] bg-espresso px-[13px] py-[7px] text-[12.5px] leading-[1.4] text-on-dark">
          {item.detail ?? ""}
        </li>
      );
    case "line":
    case "block":
      return (
        <li className="rounded-[10px] bg-card px-[12px] py-[10px] text-[12px] leading-[1.5] text-ink-2 shadow-e1">
          {item.blocks != null ? (
            <Blocks item={item} />
          ) : (
            <p>{narrate(item.code, item.outcome, item.detail)}</p>
          )}
        </li>
      );
    case "tool":
      return (
        <ToolCard
          runId={runId}
          item={item}
          selected={item.ref_id !== null && item.ref_id === selectedRef}
          onSelect={onSelectRef}
          onTrace={onTrace}
        />
      );
    case "progress":
      return (
        <li
          data-level-row="holding"
          className="flex items-center justify-between px-[2px] text-[12px] font-medium"
        >
          {item.detail ?? item.code}
          <span className="motion-safe:animate-pulse text-ink-3">Holding…</span>
        </li>
      );
    case "decision_ref":
      return (
        <li
          data-tool-card="blocked"
          className="rounded-[10px] bg-card px-[11px] pb-[9px] pt-[8px] shadow-e1"
        >
          <p className="flex items-center gap-2">
            <StatusDisc disc="warn" />
            <span className="flex-1 text-[12px] font-medium">
              {item.detail ?? "Await decision"}
            </span>
          </p>
          {item.ref_id !== null && onOpenDecision !== undefined && (
            <div className="flex justify-end pt-[4px]">
              <Button
                size="xs"
                variant="ghost"
                onClick={() => {
                  if (item.ref_id !== null) onOpenDecision(item.ref_id);
                }}
              >
                Open decision
              </Button>
            </div>
          )}
        </li>
      );
    case "question":
      // SHL-13 frame 5: the agent's question; answering and skipping are a person's (P-09-T14).
      return <QuestionCard runId={runId} item={item} />;
    case "plan":
    case "approval":
      return (
        <li
          data-ask-card={kind}
          className="rounded-[10px] bg-card px-[12px] py-[10px] text-[12.5px] shadow-ask"
        >
          <Blocks item={item} />
          {item.detail !== null && <p className="font-medium">{item.detail}</p>}
          {!acts.can("agent_run.approve_plan") && (
            <p className="pt-[6px] text-[11.5px] text-ink-3">
              Answer in the run once run commands are on for this firm.
            </p>
          )}
        </li>
      );
    case "error":
      return (
        <li
          data-tool-card="failed"
          className="rounded-[10px] bg-card px-[11px] py-[8px] shadow-e1"
        >
          <p className="flex items-center gap-2">
            <StatusDisc disc="fail" />
            <span className="text-[11.5px] font-medium text-red-ink">Failed</span>
          </p>
          <div className="pt-[4px] text-[11.5px] text-red-ink">
            <Blocks item={item} />
          </div>
        </li>
      );
    case "run_card":
      return (
        <li data-run-card="true" className="rounded-[10px] bg-card px-[12px] py-[10px] shadow-e1">
          <Blocks item={item} />
        </li>
      );
    default:
      return <li className="text-[11.5px] text-ink-3">{item.detail ?? item.code}</li>;
  }
}

/** One agent in the dock's strip (SHL-13 revision 1): its name, how it started, its state. */
export interface DockAgent {
  key: string;
  label: string;
  /** Known for the open run (its `trigger_kind`); the run list does not carry it. */
  source?: "Trigger" | "Agent column" | "Manual";
  state: AgentRunOut["state"];
}

/** How a run started, in the strip's words (C6 v1.1 `trigger_kind`). */
export function sourceOf(trigger: string | null | undefined): NonNullable<DockAgent["source"]> {
  if (trigger === "agent_column") return "Agent column";
  if (
    trigger === "agent_trigger" ||
    trigger === "engagement_trigger" ||
    trigger === "event_policy" ||
    trigger === "schedule"
  ) {
    return "Trigger";
  }
  return "Manual";
}

const AGENT_STATE: Readonly<Record<AgentRunOut["state"], string>> = {
  queued: "Queued",
  running: "Running",
  needs_input: "Needs your input",
  succeeded: "Done",
  failed: "Failed",
};

/** SHL-13 revision 1: "Agents on this engagement · n ⌄", collapsed in frames 1 to 8. */
function AgentsStrip({ agents }: { agents: readonly DockAgent[] }): JSX.Element {
  const [open, setOpen] = useState(false);
  return (
    <section aria-label="Agents on this engagement" className="mx-[10px] mb-[6px]">
      <button
        type="button"
        aria-expanded={open}
        className="flex h-[30px] w-full items-center justify-between text-[11.5px] font-medium text-ink-2"
        onClick={() => {
          setOpen(!open);
        }}
      >
        {`Agents on this engagement · ${count(agents.length)}`}
        <Icon name="chevron-down" size={12} />
      </button>
      {open && (
        <ul>
          {agents.map((a) => (
            <li key={a.key} className="flex h-[36px] items-center gap-2 text-[12.5px]">
              <Icon name="sparkles" size={12} />
              <span className="min-w-0 flex-1 truncate">{a.label}</span>
              {a.source !== undefined && (
                <span className="rounded-[6px] bg-nested px-[6px] text-[11px] leading-[20px]">
                  {a.source}
                </span>
              )}
              <StatusPill tone={a.state === "failed" ? "danger" : "neutral"}>
                {AGENT_STATE[a.state]}
              </StatusPill>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** SHL-13 frame 1: the engagement agent before its first run. */
function IdleCard({ levels }: { levels: readonly RunProjectionLevelOut[] }): JSX.Element {
  const total = levels.reduce((n, lv) => n + lv.total, 0);
  return (
    <section
      data-run-idle="true"
      className="mx-[10px] rounded-[10px] bg-shell px-[12px] py-[10px]"
    >
      <h3 className="text-[15px] font-medium">Engagement agent</h3>
      <p className="text-[12.5px] text-ink-3">
        {`Ready to run ${count(total)} workpapers across ${count(levels.length)} levels`}
      </p>
      <p className="pt-[8px] text-[12px] text-ink-2">
        Auto mode is off — I&apos;ll propose the plan and wait for your go-ahead.
      </p>
    </section>
  );
}

/** SHL-13 frame 8: a close run's card, counted by code from its one level. */
function CloseRunCard({
  levels,
  startedAt,
}: {
  levels: readonly RunProjectionLevelOut[];
  startedAt: string | null;
}): JSX.Element {
  const now = useNow();
  const total = levels.reduce((n, lv) => n + lv.total, 0);
  const done = levels.reduce((n, lv) => n + (lv.done ?? 0), 0);
  const running = levels.reduce((n, lv) => n + (lv.running ?? 0), 0);
  const minutes =
    startedAt === null
      ? null
      : Math.max(0, Math.round((now.getTime() - new Date(startedAt).getTime()) / 60_000));
  return (
    <section
      data-close-run-card="true"
      className="mx-[10px] rounded-[10px] bg-card px-[12px] py-[10px] shadow-e1"
    >
      <h3 className="text-[15px] font-medium">
        {running > 0 ? "Closing agent is running" : "Closing agent"}
      </h3>
      {running > 0 && (
        <p className="text-[12.5px] text-ink-3">{`${count(running)} tasks running at once`}</p>
      )}
      <ProgressBar
        className="mt-[8px]"
        done={done}
        total={total}
        {...(minutes === null ? {} : { right: `Started ${count(minutes)} minutes ago` })}
      />
    </section>
  );
}

/** A close run (CLS-02) draws tasks, not workpaper levels (SHL-13 frame 8). */
function isCloseRun(run: AgentRunOut | undefined): boolean {
  return run?.agent.startsWith("close") ?? false;
}

export interface RunPaneProps {
  runId: string;
  onTrace: (runId: string) => void;
  /** The rail row selected on the host page (the step's `work_item_ref`, DockSelectionStore). */
  selectedRef?: string | null;
  onSelectRef?: (ref: string) => void;
  onOpenDecision?: (ref: string) => void;
  /** The agents on this engagement for the strip under the header (the dock's run list). */
  agents?: readonly DockAgent[];
  /** P-09-T14: the engagement a new run starts on (the dock's). */
  engagementId?: string;
}

function header(view: RunViewOut | undefined): { live: boolean; ended: boolean } {
  const state = view?.run.state ?? "queued";
  const live = view !== undefined && isActive(view.run);
  const ended = TERMINAL.has(state);
  return { live, ended };
}

/** O3 "Sign off run": lists the open issues and decisions the person acknowledges. */
function SignOffDialog({
  runId,
  open,
  onOpenChange,
  issues,
  decisions,
}: {
  runId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  issues: readonly RunItemOut[];
  decisions: readonly RunItemOut[];
}): JSX.Element {
  const acts = useContext(ActsContext);
  const sign = useMutation({
    ...signOffRunMutation(),
    onSuccess: acts.done,
    onError: acts.refused,
  });
  const ids = (items: readonly RunItemOut[]): string[] =>
    items.flatMap((i) => (i.ref_id === null ? [] : [i.ref_id]));
  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Sign off run"
      confirmLabel="Sign off run"
      destructive={false}
      onConfirm={() => {
        sign.mutate({
          path: { run_id: runId },
          body: { acknowledged_issue_ids: ids(issues), acknowledged_decision_ids: ids(decisions) },
          headers: key(),
        });
      }}
    >
      {issues.length + decisions.length === 0 ? (
        <p>Nothing is open on this run.</p>
      ) : (
        <ul data-sign-off-open className="flex flex-col gap-[4px]">
          {issues.map((i) => (
            <li key={i.seq}>{`Open issue · ${i.detail ?? i.code.replaceAll("_", " ")}`}</li>
          ))}
          {decisions.map((d) => (
            <li key={d.seq}>{`Open decision · ${d.detail ?? d.code.replaceAll("_", " ")}`}</li>
          ))}
        </ul>
      )}
    </ConfirmDialog>
  );
}

function HeaderAction({
  view,
  idle,
  ended,
  engagementId,
  items,
}: {
  view: RunViewOut | undefined;
  idle: boolean;
  ended: boolean;
  engagementId: string | undefined;
  items: readonly RunItemOut[];
}): JSX.Element | null {
  const acts = useContext(ActsContext);
  const [confirm, setConfirm] = useState(false);
  const start = useMutation({
    ...startEngagementRunMutation(),
    onSuccess: acts.done,
    onError: acts.refused,
  });
  if (isCloseRun(view?.run)) {
    const n = view?.header?.run_number;
    return (
      <Button size="sm" variant="ghost" disabled title="The run picker arrives with P-09-T13">
        {`Run ${n == null ? "" : count(n)}`}
        <Icon name="chevron-down" size={12} />
      </Button>
    );
  }
  if (idle) {
    if (!acts.can("agent_run.start") || engagementId === undefined) return null;
    return (
      <Button
        size="sm"
        disabled={start.isPending}
        onClick={() => {
          start.mutate({
            path: { engagement_id: engagementId },
            body: { work_item_ref: view?.header?.work_item_ref ?? null, auto: false },
            headers: key(),
          });
        }}
      >
        <Icon name="play" size={12} />
        Run
      </Button>
    );
  }
  if (!acts.can("agent_run.sign_off")) return null;
  const runId = view?.run.id ?? "";
  return (
    <>
      <Button
        size="sm"
        variant="secondary"
        disabled={!ended}
        title={ended ? "Only a person signs off a run" : "A run is signed off once it has ended"}
        onClick={() => {
          setConfirm(true);
        }}
      >
        Sign off run
      </Button>
      <SignOffDialog
        runId={runId}
        open={confirm}
        onOpenChange={setConfirm}
        issues={items.filter((i) => i.session_kind === "error" || i.kind === "failure")}
        decisions={items.filter((i) => i.session_kind === "decision_ref")}
      />
    </>
  );
}

/** SHL-13: one run in the dock. */
export function RunPane({
  runId,
  onTrace,
  selectedRef,
  onSelectRef,
  onOpenDecision,
  agents,
  engagementId,
}: RunPaneProps): JSX.Element {
  const queryClient = useQueryClient();
  const v2 = useFlag("agent_runtime.v2") === true;
  const view = useQuery({
    ...agentRunOptions({ path: { run_id: runId } }),
    retry: false,
    refetchInterval: (q) =>
      q.state.data !== undefined && isActive(q.state.data.run) ? POLL_MS : false,
    refetchIntervalInBackground: false,
  });
  const feed = useRunFeed(runId);
  const { live, ended } = header(view.data);
  const allowed = new Set(view.data?.allowed_actions ?? []);
  const acts: RunActs = {
    can: (action) => v2 && allowed.has(action),
    refused: (error) => {
      toast.show(refusalWords(error));
    },
    done: () => {
      void queryClient.invalidateQueries();
    },
  };
  const approve = useMutation({
    ...approveRunPlanMutation(),
    onSuccess: acts.done,
    onError: acts.refused,
  });
  const steer = useMutation({
    ...redirectRunMutation(),
    onSuccess: acts.done,
    onError: acts.refused,
  });
  const [message, setMessage] = useState("");
  const canSteer = live && acts.can("agent_run.control");
  if (view.isError) {
    return (
      <p data-run-pane="not-allowed" className="p-[12px] text-dense text-ink-3">
        You can&apos;t open this run.
      </p>
    );
  }
  const levels = view.data?.levels ?? [];
  const idle = view.data?.run.state === "queued" && feed.items.length === 0;
  const planReady =
    view.data?.run.state === "needs_input" && view.data.header?.blocked_on?.kind === "approval";
  const close = isCloseRun(view.data?.run);
  return (
    <ActsContext.Provider value={acts}>
      <section
        data-run-pane={view.data?.run.state ?? "loading"}
        className="flex min-h-0 flex-1 flex-col"
      >
        <header className="relative flex h-[46px] items-center justify-center">
          {live && (
            <span
              data-live-dot="true"
              aria-label="Run active"
              className="absolute left-[12px] size-[8px] rounded-full bg-green"
            />
          )}
          <h2 className="text-[14.5px] font-medium">Agent</h2>
          <div className="absolute right-[10px]">
            <HeaderAction
              view={view.data}
              idle={idle}
              ended={ended}
              engagementId={engagementId}
              items={feed.items}
            />
          </div>
        </header>
        {agents !== undefined && agents.length > 0 && !close && (
          <AgentsStrip
            agents={agents.map((a) =>
              a.key === view.data?.run.agent
                ? { ...a, source: sourceOf(view.data.header?.trigger_kind) }
                : a,
            )}
          />
        )}
        {view.isPending ? (
          <Skeleton className="m-[10px] h-[120px]" />
        ) : close ? (
          <CloseRunCard levels={levels} startedAt={view.data.run.started_at} />
        ) : (
          <>
            {idle && <IdleCard levels={levels} />}
            {levels.length > 0 && <ProjectionStrip levels={levels} planReady={planReady} />}
          </>
        )}
        <ol
          aria-label="Run thread"
          className="flex min-h-0 flex-1 flex-col gap-[8px] overflow-y-auto p-[12px]"
        >
          {feed.items.map((item) =>
            close && item.session_kind === "tool" ? (
              <TaskRow key={item.seq} item={item} />
            ) : (
              <ThreadItem
                key={item.seq}
                runId={runId}
                item={item}
                selectedRef={selectedRef}
                onSelectRef={onSelectRef}
                onOpenDecision={onOpenDecision}
                onTrace={() => {
                  onTrace(runId);
                }}
              />
            ),
          )}
        </ol>
        {planReady && acts.can("agent_run.approve_plan") && (
          <div data-quick-replies="true" className="mx-[10px] mb-[6px] flex gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={approve.isPending || view.data?.header?.plan_version == null}
              onClick={() => {
                const version = view.data?.header?.plan_version;
                if (version == null) return;
                approve.mutate({
                  path: { run_id: runId },
                  body: { expected_version: version },
                  headers: key(),
                });
              }}
            >
              yes, run it
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled
              title="Editing the plan arrives with P-09-T14"
            >
              Change order…
            </Button>
          </div>
        )}
        <form
          aria-label="Message the agent"
          className="mx-[10px] mb-[10px] flex h-[38px] items-center gap-2 rounded-full border-[0.5px] border-hair bg-nested px-[12px]"
          onSubmit={(e) => {
            e.preventDefault();
            if (!canSteer || message.trim() === "") return;
            steer.mutate(
              { path: { run_id: runId }, body: { body: message.trim() }, headers: key() },
              {
                onSuccess: () => {
                  setMessage("");
                },
              },
            );
          }}
        >
          <Icon name="paperclip" size={14} />
          <input
            aria-label="Message"
            placeholder="Message"
            disabled={!canSteer || steer.isPending}
            value={message}
            onChange={(e) => {
              setMessage(e.target.value);
            }}
            className="min-w-0 flex-1 bg-transparent text-[12.5px] placeholder:text-ink-3"
          />
          <button
            type="submit"
            disabled={!canSteer || steer.isPending || message.trim() === ""}
            aria-label="Send"
            className="size-[26px] rounded-full bg-nested"
          >
            <Icon name="arrow-up" size={13} />
          </button>
        </form>
      </section>
    </ActsContext.Provider>
  );
}
