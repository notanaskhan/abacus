import type { RunItemOut, RunProjectionLevelOut, RunViewOut } from "@abacus/api-client";
import { getAgentRunOptions } from "@abacus/api-client/query";
import {
  AgentBlocks,
  type AgentBlocksPayload,
  Button,
  Icon,
  type IconName,
  Skeleton,
  StatusPill,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { narrate } from "./narrate";
import { isActive, POLL_MS, useRunFeed } from "./runFeed";

// SHL-13 run pane (P-09-T09; SPEC-648 Story 1.1 to 1.3; handoff SHL-13 frames 1 to 8): one run in
// the 330 dock: the header with the live dot and "Sign off run", the run projection by level
// (code's counts from C6 v1.1's `levels`), and the thread in the C6 v2 wire set: the person's
// bubbles, narration through AgentBlocks, tool cards in their six states, the level row, the
// decision and ask cards, failures and the close run card. The composer and every human action
// ("Sign off run", plan and question answers, Retry) are bound to P-10's run commands by P-09-T14;
// until then they render disabled. Nothing here decides for a person (ADR-005; frontend rule 3).

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
  | "dispatched"
  | "running"
  | "waiting_on_inputs"
  | "blocked"
  | "succeeded"
  | "failed";

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
  return `Run projection · ${total} workpapers · ${levels.length} levels`;
}

/** The ink-3 tail of a level row: "1 blocked · 1 running" (and failures). */
export function levelTail(level: RunProjectionLevelOut): string | null {
  const parts: string[] = [];
  if (level.blocked > 0) parts.push(`${level.blocked} blocked`);
  if (level.running > 0) parts.push(`${level.running} running`);
  if (level.failed > 0) parts.push(`${level.failed} failed`);
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
      <Icon name={icon} size={15} {...(disc === "run" ? { className: "motion-safe:animate-spin" } : {})} />
    </span>
  );
}

function ProjectionStrip({ levels }: { levels: readonly RunProjectionLevelOut[] }): JSX.Element {
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
        <Icon name="chevron-down" size={12} />
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
                <span className="min-w-0 flex-1">{LEVEL_LABEL[lv.level] ?? `Level ${lv.level}`}</span>
                {tail !== null && <span className="text-[11px] text-ink-3">{tail}</span>}
                <span
                  className={
                    complete
                      ? "rounded-full bg-green-tint px-[6px] text-green-ink tabular-nums"
                      : "rounded-full bg-chip px-[6px] tabular-nums"
                  }
                >
                  {complete ? `${lv.done} of ${lv.total} ✓` : `${lv.done} of ${lv.total}`}
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
  return <AgentBlocks blocks={item.blocks as AgentBlocksPayload} facts={{}} />;
}

function ToolCard({
  item,
  selected,
  onSelect,
  onTrace,
}: {
  item: RunItemOut;
  selected: boolean;
  onSelect?: ((ref: string) => void) | undefined;
  onTrace: () => void;
}): JSX.Element {
  const state = toolState(item.outcome);
  const look = TOOL_STATE[state];
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
          {state === "failed" && (
            <Button size="xs" variant="secondary" disabled>
              Retry
            </Button>
          )}
          <Button size="xs" variant="ghost" onClick={onTrace}>
            Open trace
          </Button>
        </div>
      )}
    </li>
  );
}

function ThreadItem({
  item,
  selectedRef,
  onSelectRef,
  onTrace,
  onOpenDecision,
}: {
  item: RunItemOut;
  selectedRef?: string | null | undefined;
  onSelectRef?: ((ref: string) => void) | undefined;
  onTrace: () => void;
  onOpenDecision?: ((ref: string) => void) | undefined;
}): JSX.Element {
  const kind = item.session_kind ?? "notice";
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
            <span className="flex-1 text-[12px] font-medium">{item.detail ?? "Await decision"}</span>
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
    case "plan":
    case "approval":
      return (
        <li
          data-ask-card={kind}
          className="rounded-[10px] bg-card px-[12px] py-[10px] text-[12.5px] shadow-ask"
        >
          <Blocks item={item} />
          {item.detail !== null && <p className="font-medium">{item.detail}</p>}
          <p className="pt-[6px] text-[11.5px] text-ink-3">
            Answer in the run once run commands are on for this firm.
          </p>
        </li>
      );
    case "error":
      return (
        <li data-tool-card="failed" className="rounded-[10px] bg-card px-[11px] py-[8px] shadow-e1">
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

export interface RunPaneProps {
  runId: string;
  onTrace: (runId: string) => void;
  /** The rail row selected on the host page (the step's `work_item_ref`, DockSelectionStore). */
  selectedRef?: string | null;
  onSelectRef?: (ref: string) => void;
  onOpenDecision?: (ref: string) => void;
}

function header(view: RunViewOut | undefined): { live: boolean; ended: boolean; canSign: boolean } {
  const state = view?.run.state ?? "queued";
  const live = view !== undefined && isActive(view.run);
  const ended = TERMINAL.has(state);
  const canSign = ended && (view?.allowed_actions.includes("agent_run.sign_off") ?? false);
  return { live, ended, canSign };
}

/** SHL-13: one run in the dock. */
export function RunPane({
  runId,
  onTrace,
  selectedRef,
  onSelectRef,
  onOpenDecision,
}: RunPaneProps): JSX.Element {
  const view = useQuery({
    ...getAgentRunOptions({ path: { run_id: runId } }),
    retry: false,
    refetchInterval: (q) => (q.state.data !== undefined && isActive(q.state.data.run) ? POLL_MS : false),
    refetchIntervalInBackground: false,
  });
  const feed = useRunFeed(runId);
  const { live, canSign } = header(view.data);
  if (view.isError) {
    return (
      <p data-run-pane="not-allowed" className="p-[12px] text-dense text-ink-3">
        You can't open this run.
      </p>
    );
  }
  return (
    <section data-run-pane={view.data?.run.state ?? "loading"} className="flex min-h-0 flex-1 flex-col">
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
          <Button size="sm" variant="secondary" disabled={!canSign} title="Only a person signs off a run">
            Sign off run
          </Button>
        </div>
      </header>
      {view.isPending ? (
        <Skeleton className="m-[10px] h-[120px]" />
      ) : view.data.levels.length > 0 ? (
        <ProjectionStrip levels={view.data.levels} />
      ) : null}
      <ol aria-label="Run thread" className="flex min-h-0 flex-1 flex-col gap-[8px] overflow-y-auto p-[12px]">
        {feed.items.map((item) => (
          <ThreadItem
            key={item.seq}
            item={item}
            selectedRef={selectedRef}
            onSelectRef={onSelectRef}
            onOpenDecision={onOpenDecision}
            onTrace={() => {
              onTrace(runId);
            }}
          />
        ))}
      </ol>
      <form
        aria-label="Message the agent"
        className="mx-[10px] mb-[10px] flex h-[38px] items-center gap-2 rounded-full border-[0.5px] border-hair bg-nested px-[12px]"
        onSubmit={(e) => {
          e.preventDefault();
        }}
      >
        <Icon name="paperclip" size={14} />
        <input
          aria-label="Message"
          placeholder="Message"
          disabled
          className="min-w-0 flex-1 bg-transparent text-[12.5px] placeholder:text-ink-3"
        />
        <button type="submit" disabled aria-label="Send" className="size-[26px] rounded-full bg-nested">
          <Icon name="arrow-up" size={13} />
        </button>
      </form>
    </section>
  );
}
