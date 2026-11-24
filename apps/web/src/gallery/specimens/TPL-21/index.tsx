// TPL-21 "Board — FY2026 Financial Statement Audit, Granite Peak Outdoor Supply" (F-08-T23;
// TASK-8929; handoff TPL-21 a–f; DEC-5931): T19 BoardLayout on the Granite Peak audit-program seed
// (fixtures/seed/granite-peak-fy2026-board.ts, footed by its test). Thu Sep 24, 2026, Cole Hart:
//   a 9:30 AM default (4 · 5 · 2 · 2; Planning collapsed "8 of 8") · b 10:05 AM dragging
//   BH-FS-430 over In progress (preview 3 / 6) · c 10:05 AM dropped (3 · 6 · 2 · 2; Agent running
//   40%; the SHL-13 dock and the toast) · d 9:42 AM Hannah Leclerc's drop guard on BH-FS-320 ·
//   e Binder view ("Preparer 12 of 21 · Reviewer 10 of 21") · f the four overlay states on
//   BH-FS-440 (specimen, not seed). Nothing on the board signs off. Gallery only.
import {
  BoardCard,
  type BoardLayoutCard,
  type BoardLayoutColumn,
  BoardLayout,
  type BoardLayoutLane,
  type BoardCardProps,
} from "@abacus/ui";
import type { JSX } from "react";
import {
  AUDIT_PROGRAM_BOARD,
  afterBhFs430Move,
} from "../../../fixtures/seed/granite-peak-fy2026-board";
import type { FixtureParams } from "../../fixture-mode";
import { C } from "./copy";

type BoardDraft = Parameters<typeof afterBhFs430Move>[0];
type BoardCardDraft = BoardDraft["cards"][number];

export const TPL21_STATES = ["a", "b", "c", "d", "e", "f"] as const;
type State = (typeof TPL21_STATES)[number];

const NAMES: Record<string, string> = {
  CH: "Cole Hart",
  SB: "Simone Baptiste",
  HL: "Hannah Leclerc",
};
const COLUMN_WORDS: Record<BoardCardDraft["column"], string> = {
  not_started: "Not started",
  in_progress: "In progress",
  in_review: "In review",
  complete: "Complete",
};

function agentOf(card: BoardCardDraft): NonNullable<BoardCardProps["agent"]> {
  if (card.agent === "done") return { state: "done" };
  if (card.agent === "not_run" || card.agent === undefined) return { state: "not_run" };
  return card.agent.running
    ? {
        state: "running",
        pct: card.agent.pct,
        ...(card.ref === "BH-FS-430" ? { tip: C.runTip } : {}),
      }
    : { state: "progress", pct: card.agent.pct };
}

function slot(level: string, role: string, who: string | null) {
  return { level, role, signer: who === null ? null : (NAMES[who] ?? who), at: null };
}

function card(c: BoardCardDraft): BoardLayoutCard {
  return {
    id: c.ref,
    lane: c.area ?? "planning",
    column: c.column,
    version: 1,
    title: c.title,
    code: c.ref,
    owner: c.owner,
    ownerName: NAMES[c.owner] ?? c.owner,
    metrics: [c.metrics.days, c.metrics.evidence, c.metrics.requests, c.metrics.todos],
    agent: agentOf(c),
    p: slot("L1", "Preparer", c.signoffs.preparer),
    r: slot("L2", "Reviewer", c.signoffs.reviewer),
    ...(c.overlay === "needs_input" ? { flag: "input" as const } : {}),
    ...(c.overlay === "waiting_on_client" ? { flag: "client" as const } : {}),
    ...(c.overlay === "agent_running" ? { spin: true } : {}),
    ...(c.sub ? { sub: c.sub } : {}),
    todos: c.signoffs.preparer ? "Done" : "—",
    status: COLUMN_WORDS[c.column],
  };
}

function columns(board: BoardDraft, preview?: { from: string; to: string }): BoardLayoutColumn[] {
  const disc = {
    not_started: "todo",
    in_progress: "half",
    in_review: "dot",
    complete: "done",
  } as const;
  return (Object.keys(COLUMN_WORDS) as BoardCardDraft["column"][]).map((k) => {
    const n = board.cards.filter((c) => c.column === k).length;
    const adjust = preview ? (k === preview.from ? -1 : k === preview.to ? 1 : 0) : 0;
    return {
      key: k,
      label: COLUMN_WORDS[k],
      count: n + adjust,
      disc: disc[k],
      // The drop guard: Complete needs a reviewer sign-off (SHL-12); the server refuses it.
      ...(k === "complete" ? { accepts: true } : {}),
    };
  });
}

function lanes(board: BoardDraft): BoardLayoutLane[] {
  return (board.areas ?? []).map((a) => ({
    key: a.key,
    title: a.title,
    meta: a.programs === 1 ? "1 program" : `${String(a.programs)} programs`,
    ...(a.phase === "planning"
      ? { done: `${String(a.programs)} of ${String(a.programs)}`, collapsed: true }
      : {}),
  }));
}

function navigator(selected: string) {
  const areas = AUDIT_PROGRAM_BOARD.areas;
  const planning = areas.filter((a) => a.phase === "planning").reduce((n, a) => n + a.programs, 0);
  const execution = areas.filter((a) => a.phase === "execution");
  return {
    title: C.programs,
    items: [
      { key: "all", label: C.allPrograms, count: AUDIT_PROGRAM_BOARD.binder.total },
      { key: "planning", label: C.planning, count: planning },
      {
        key: "execution",
        label: C.execution,
        count: execution.reduce((n, a) => n + a.programs, 0),
      },
      ...execution.map((a) => ({
        key: a.key,
        label: a.title,
        count: a.programs,
        depth: 1 as const,
      })),
    ],
    selected,
  };
}

function Overlays(): JSX.Element {
  const base = AUDIT_PROGRAM_BOARD.cards.find((c) => c.ref === "BH-FS-440");
  if (base === undefined) return <></>;
  const props = card(base);
  const rest: BoardCardProps = {
    title: props.title,
    code: props.code,
    owner: props.owner,
    ownerName: props.ownerName,
    ...(props.metrics ? { metrics: props.metrics } : {}),
    ...(props.agent ? { agent: props.agent } : {}),
    ...(props.p ? { p: props.p } : {}),
    ...(props.r ? { r: props.r } : {}),
  };
  return (
    <section aria-label={C.overlays} data-overlays="" className="flex flex-col gap-[8px] p-[12px]">
      <h2 className="text-[12px] text-ink-3">{C.overlays}</h2>
      <div className="flex gap-[10px]">
        <BoardCard {...rest} flag="input" />
        <BoardCard {...rest} flag="client" />
        <BoardCard {...rest} spin agent={{ state: "running", pct: 70 }} />
        <BoardCard {...rest} sentBy="HL" />
      </div>
    </section>
  );
}

export function Tpl21Artboard({ params }: { params: FixtureParams }): JSX.Element {
  const state: State = TPL21_STATES.find((s) => s === params.st) ?? "a";
  const board = state === "c" ? afterBhFs430Move(AUDIT_PROGRAM_BOARD) : AUDIT_PROGRAM_BOARD;
  const preview = state === "b" ? { from: "not_started", to: "in_progress" } : undefined;
  return (
    <div data-artboard={state} className="relative flex h-[860px] w-[1400px] flex-col bg-shell">
      <header className="flex h-[42px] flex-none items-center justify-center gap-[8px] text-[15px]">
        <span className="font-medium">{C.record}</span>
        <span className="text-ink-2">{C.client}</span>
      </header>
      <nav
        aria-label={C.tabs}
        className="flex h-[44px] flex-none items-center justify-center gap-[12px] text-[13.5px] text-ink-2"
      >
        {C.tabWords.map((t) => (
          <span key={t} className={t === "Board" ? "font-medium text-ink" : ""}>
            {t}
          </span>
        ))}
      </nav>
      {state === "f" ? (
        <Overlays />
      ) : (
        <BoardLayout
          variant="audit"
          label={C.programs}
          view={state === "e" ? "binder" : "board"}
          columns={columns(board, preview)}
          lanes={lanes(board)}
          cards={board.cards.map(card)}
          filters={[
            { key: "agents", label: "Agents", icon: "atom", options: [], value: null },
            { key: "phase", label: "Phase", options: [], value: null },
            { key: "area", label: "Audit area", icon: "layers", options: [], value: null },
            { key: "owner", label: "Owner", icon: "user", options: [], value: null },
          ]}
          runOnMove={{ allowed: true, on: true, allowedTip: C.allowedTip }}
          navigator={navigator(state === "b" ? "payables" : "all")}
          binderFooter={C.binderFooter(AUDIT_PROGRAM_BOARD.binder)}
          {...(state === "b" ? { forceDrag: { cardId: "BH-FS-430", over: "in_progress" } } : {})}
          onMoveIntent={(intent) =>
            Promise.resolve(
              intent.toColumn === "complete"
                ? { kind: "guarded", requires: "sign_off", text: C.guard }
                : intent.runAgent
                  ? { kind: "dispatched", runId: "run", text: C.dropped }
                  : { kind: "moved" },
            )
          }
        />
      )}
      {state === "c" ? (
        <aside
          aria-label={C.dock}
          data-dock=""
          className="absolute bottom-[60px] right-[12px] w-[330px] rounded-pane bg-card p-[12px] shadow-e2"
        >
          <p className="text-[12.5px]">{C.dockLine}</p>
          <p className="mt-[4px] text-[12.5px] font-medium">{C.openSession}</p>
        </aside>
      ) : null}
      {state === "c" || state === "d" ? (
        <p
          role="status"
          data-toast=""
          className="absolute bottom-[12px] left-1/2 flex h-[36px] -translate-x-1/2 items-center gap-[8px] rounded-pane bg-espresso px-[14px] text-[12.5px] text-on-dark"
        >
          {state === "c" ? C.dropped : C.guard}
          {state === "d" ? <span className="font-medium">{C.openSignOff}</span> : null}
        </p>
      ) : null}
    </div>
  );
}
