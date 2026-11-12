// TXP-00 · Return › Agent, entity returns (T-05-T29; docs/screens/TXP-00.md; handoff TXP-00 A–E):
// the shoebox → workbook run surface on T2 (rail 330 + canvas, no dock). The rail reads General
// Information, Links and Team; the canvas's RunCard heads six task groups of ten rows with a
// StatusDisc each. A is Run 2 complete with 11 open items; B Run 3 running (three rows at once,
// spinners in ink-2 and the word "Running…", never amber); C idle with ▶ Run; D waiting on the
// §706(d) answer (the chat-ask QuestionCard above the composer); E the import stopped (Retry ·
// Reconnect · View run). Running and waiting rows differ in words and glyphs, not colour alone.
// The composer hands off to TAX-08. Every human verb is the person's; the agent never approves.
import { Button, Icon, QuestionCard, Spinner, StatusDisc } from "@abacus/ui";
import type { JSX } from "react";
import { COPY, GROUPS, type GroupCopy, QUESTION_706D, type TaskCopy } from "./copy";

export type Txp00Frame = "a" | "b" | "c" | "d" | "e";
type RowState = "done" | "warn" | "run" | "todo" | "fail";

const RUN3_RUNNING = new Set(["capital_m2", "federal_k1s", "state_k1s_k3s"]);

/** A row's state in a frame (the handoff's A to E). */
export function rowState(frame: Txp00Frame, task: TaskCopy): RowState {
  if (frame === "c") return "todo";
  if (frame === "e") return task.key === "import_trial_balance" ? "fail" : "todo";
  if (frame === "d") {
    if (task.key === "interim_closing_706d") return "warn";
    return ["import_trial_balance", "map_lines"].includes(task.key) ? "done" : "todo";
  }
  if (frame === "b" && RUN3_RUNNING.has(task.key)) return "run";
  return task.open > 0 ? "warn" : "done";
}

function rowMeta(frame: Txp00Frame, task: TaskCopy, state: RowState): string {
  if (state === "todo") return COPY.notStarted;
  if (state === "run") return task.key === "capital_m2" ? COPY.runningCapital : COPY.runningK1;
  if (state === "warn" && frame === "d") return COPY.waiting;
  return task.meta;
}

/** Open items across the run (A: 1 + 1 + 2 + 4 + 1 + 2 = 11, the Issues badge). */
export function openItems(groups: readonly GroupCopy[] = GROUPS): number {
  return groups.reduce((n, g) => n + g.tasks.reduce((m, t) => m + t.open, 0), 0);
}

function Disc({ state }: { state: RowState }): JSX.Element {
  if (state === "run") {
    return <Spinner size={15} label="Running" showLabel={false} />;
  }
  const disc = { done: "done", warn: "warn", todo: "todo", fail: "fail" } as const;
  return <StatusDisc state={disc[state]} size={17} />;
}

export interface TXP00Props {
  frame: Txp00Frame;
  still?: boolean;
  onRun?: () => void;
  onReRun?: (scope: "task" | "group", key: string) => void;
  onRetry?: (taskKey: string) => void;
  onReconnect?: () => void;
  onViewRun?: () => void;
  onViewWork?: (taskKey: string) => void;
  onOpenItems?: (taskKey: string) => void;
  onAnswer?: (answer: unknown) => void;
  onComposer?: () => void;
}

function RunCard({ frame, onRun }: { frame: Txp00Frame; onRun?: () => void }): JSX.Element {
  const [title, sub, progress, started, pct] =
    frame === "b"
      ? [COPY.runningTitle, COPY.runningSub, COPY.runningProgress, COPY.runningStarted, 70]
      : frame === "c"
        ? [COPY.idleTitle, COPY.idleSub, null, null, 0]
        : frame === "a"
          ? [
              COPY.completeTitle,
              COPY.completeSub,
              COPY.completeProgress,
              COPY.completeStarted,
              100,
            ]
          : [COPY.idleTitle, null, null, null, 20];
  return (
    <div
      data-kit="RunCard"
      data-frame={frame}
      className="px-[16px] pt-[14px] pb-[13px] hairline-b"
    >
      <div className="flex items-start gap-[12px]">
        <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
          <h3 className="text-[15px] font-medium">{title}</h3>
          {frame === "d" ? (
            <p data-waiting className="flex items-center gap-[6px] text-[12.5px] text-ink-3">
              <span aria-hidden="true" className="size-[8px] rounded-pill bg-amber" />
              {COPY.waiting}
            </p>
          ) : frame === "e" ? (
            <p className="text-[12.5px] font-medium text-red-ink">{COPY.failedTitle}</p>
          ) : sub !== null ? (
            <p className="text-[12.5px] text-ink-3">{sub}</p>
          ) : null}
        </div>
        {frame === "c" ? (
          <Button variant="primary" size="lg" onClick={onRun}>
            <Icon name="play" size={12} />
            {COPY.runPrimary}
          </Button>
        ) : frame === "b" ? (
          <span className="flex size-[32px] items-center justify-center rounded-pill bg-card shadow-e1">
            <Spinner size={15} label="Running" showLabel={false} />
          </span>
        ) : frame === "a" ? (
          <span className="flex size-[32px] items-center justify-center rounded-pill bg-card shadow-e1">
            <StatusDisc state="done" size={15} />
          </span>
        ) : null}
      </div>
      {progress !== null ? (
        <div className="mt-[12px] flex items-center gap-[10px] text-[12.5px]">
          <span className="text-ink-2">{progress}</span>
          <span
            role="progressbar"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={progress}
            className="h-[3px] flex-1 rounded-pill bg-chip"
          >
            <span
              className="block h-full rounded-pill bg-espresso"
              style={{ width: `${String(pct)}%` }}
            />
          </span>
          <span className="text-ink-4">{started}</span>
        </div>
      ) : null}
    </div>
  );
}

function TaskGroup({
  group,
  frame,
  props,
}: {
  group: GroupCopy;
  frame: Txp00Frame;
  props: TXP00Props;
}): JSX.Element {
  const states = group.tasks.map((t) => rowState(frame, t));
  const done = states.filter((s) => s === "done" || s === "warn").length;
  const running = states.includes("run");
  const open = group.tasks.reduce((n, t) => n + t.open, 0);
  return (
    <section data-group={group.key} aria-label={group.title}>
      <header className="flex items-center gap-[10px] bg-shell py-[10px] pr-[10px] pl-[13px]">
        <span className="flex min-w-0 flex-1 items-baseline gap-[8px]">
          <span className="text-[14px] font-medium">{group.title}</span>
          {frame === "a" || frame === "b" ? (
            <span className="text-[12px] text-ink-3">
              {open > 0 ? `${String(open)} open` : ""}
            </span>
          ) : null}
        </span>
        {frame === "a" || frame === "b" ? (
          <span
            data-badge={running ? "running" : "done"}
            className={`flex h-[21px] items-center gap-[5px] rounded-pill px-[8px] text-[11.5px] ${
              running ? "bg-nested text-ink-2" : "bg-green text-on-dark"
            }`}
          >
            {`${String(done)} of ${String(group.tasks.length)}`}
            {running ? (
              <Spinner size={12} label="Running" showLabel={false} />
            ) : (
              <Icon name="check" size={12} />
            )}
          </span>
        ) : null}
        <Button variant="ghost" size="sm" onClick={() => props.onReRun?.("group", group.key)}>
          {COPY.runMenu}
        </Button>
      </header>
      <ul>
        {group.tasks.map((task, i) => {
          const state = states[i] ?? "todo";
          return (
            <li
              key={task.key}
              data-task={task.key}
              data-state={state}
              className="flex items-start gap-[10px] bg-card pt-[8px] pr-[12px] pb-[9px] pl-[13px] hairline-t hover:bg-nested"
            >
              <Disc state={state} />
              <div className="flex min-w-0 flex-1 flex-col gap-[2px]">
                <span className="text-[13.5px]">{task.name}</span>
                {state === "fail" ? (
                  <>
                    <span className="text-[12.5px] font-medium text-red-ink">
                      {COPY.failedTitle}
                    </span>
                    <span className="text-[12.5px] text-ink-2">{COPY.failedBody}</span>
                  </>
                ) : (
                  <span className="text-[11.5px] text-ink-3">{rowMeta(frame, task, state)}</span>
                )}
              </div>
              {state === "fail" ? (
                <span className="flex gap-[6px]">
                  <Button variant="secondary" size="sm" onClick={() => props.onRetry?.(task.key)}>
                    {COPY.retry}
                  </Button>
                  <Button variant="secondary" size="sm" onClick={props.onReconnect}>
                    {COPY.reconnect}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={props.onViewRun}>
                    {COPY.viewRun}
                  </Button>
                </span>
              ) : (
                <span className="flex gap-[6px]">
                  {task.open > 0 && (frame === "a" || frame === "b") ? (
                    <Button variant="ghost" size="sm" onClick={() => props.onViewWork?.(task.key)}>
                      {COPY.viewWork}
                    </Button>
                  ) : null}
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={state === "run"}
                    aria-label={`${COPY.run} ${task.name}`}
                    onClick={() => props.onReRun?.("task", task.key)}
                  >
                    {COPY.run}
                  </Button>
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function TXP00(props: TXP00Props): JSX.Element {
  const { frame } = props;
  return (
    <div
      data-screen="TXP-00"
      data-frame={frame}
      className="flex min-h-0 flex-1 gap-[10px] p-[10px]"
    >
      <aside
        aria-label={COPY.rail}
        style={{ width: 330 }}
        className="flex flex-none flex-col rounded-pane bg-card shadow-e2"
      >
        <h2 className="flex h-[46px] items-center justify-center text-[14.5px] font-medium hairline-b">
          {COPY.rail}
        </h2>
        <h3 className="flex h-[31px] items-center bg-band-hd px-[14px] text-body font-medium">
          {COPY.links}
        </h3>
        <h3 className="flex h-[31px] items-center bg-band-hd px-[14px] text-body font-medium">
          {COPY.team}
        </h3>
      </aside>
      <section
        aria-label={COPY.workbook}
        className="relative flex min-w-0 flex-1 flex-col rounded-pane bg-card shadow-e2"
      >
        <h2 className="flex h-[46px] items-center justify-center gap-[8px] text-[14.5px] font-medium hairline-b">
          {frame === "b" ? (
            <span aria-hidden="true" data-live className="size-[8px] rounded-pill bg-green" />
          ) : null}
          {COPY.workbook}
        </h2>
        <RunCard frame={frame} {...(props.onRun ? { onRun: props.onRun } : {})} />
        <div className="min-h-0 flex-1 overflow-y-auto">
          {GROUPS.map((g) => (
            <TaskGroup key={g.key} group={g} frame={frame} props={props} />
          ))}
        </div>
        {frame === "d" ? (
          <div className="mx-[16px] mb-[9px]">
            <QuestionCard
              question={QUESTION_706D}
              onAnswer={(a) => props.onAnswer?.(a)}
              {...(props.onComposer ? { onEscape: props.onComposer } : {})}
            />
          </div>
        ) : null}
        {frame === "b" ? (
          <div
            data-running-pill
            className="absolute bottom-[60px] left-1/2 flex h-[43px] -translate-x-1/2 items-center gap-[8px] rounded-pill bg-card px-[16px] shadow-e3"
          >
            <Spinner size={15} label="Running" showLabel={false} />
            <span className="text-[13px]">{COPY.runningPill}</span>
          </div>
        ) : null}
        <button
          type="button"
          data-composer
          onClick={props.onComposer}
          className="m-[10px] flex h-[38px] items-center gap-[8px] rounded-pill bg-card px-[12px] text-left text-[13px] text-ink-4 shadow-e1"
        >
          <Icon name="paperclip" size={14} className="text-ink-3" />
          {COPY.composer}
        </button>
      </section>
    </div>
  );
}

/** The frame a return's runs put the Agent tab in: no run is idle (C); the newest run running is
 * B, waiting on an answer D, failed E, otherwise complete A. */
export function frameOf(runs: readonly { state: string }[]): Txp00Frame {
  const newest = runs[0];
  if (newest === undefined) return "c";
  if (newest.state === "running" || newest.state === "queued") return "b";
  if (newest.state === "waiting_on_inputs" || newest.state === "awaiting_answer") return "d";
  if (newest.state === "failed") return "e";
  return "a";
}
