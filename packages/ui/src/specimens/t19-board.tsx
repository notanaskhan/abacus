// T19 Board template (F-08-T22; DEC-5930; handoff T19 a–l): placeholder content only, as the
// template's spec draws it ("Area A · 2 programs", "Area B · 1 program", "Program one/two/three",
// PRG-100/110/120, metrics "—"). TPL-21 (F-08-T23) is the seeded Granite Peak specimen.
//   a default · b dragging · c dropped with a run · d drop guard · e filtered · f empty
//   g loading · h control set (6 × 196, navigator rail, run on move off by policy)
//   i Binder view · j Sheet view · k returns · l close task groups (B collapsed "1 of 1")
import { type JSX, useState } from "react";
import {
  BoardLayout,
  type BoardLayoutCard,
  type BoardLayoutColumn,
  type BoardLayoutLane,
  type BoardLayoutProps,
  type BoardView,
} from "../board";
import { Sheet } from "./frame";

export const T19_STATES = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l"] as const;
export type T19State = (typeof T19_STATES)[number];

const AUDIT_COLUMNS: readonly BoardLayoutColumn[] = [
  { key: "not_started", label: "Not started", count: 1, disc: "todo" },
  { key: "in_progress", label: "In progress", count: 1, disc: "half" },
  { key: "in_review", label: "In review", count: 1, disc: "dot" },
  { key: "complete", label: "Complete", count: 0, disc: "done" },
];
const CONTROL_COLUMNS: readonly BoardLayoutColumn[] = [
  { key: "not_started", label: "Not started", count: 1, disc: "todo" },
  { key: "testing", label: "Testing", count: 1, disc: "running" },
  { key: "pending", label: "Pending", count: 0, disc: "muted" },
  { key: "preparer_review", label: "Preparer review", count: 1, disc: "half" },
  { key: "manager_review", label: "Manager review", count: 0, disc: "half" },
  { key: "review_complete", label: "Review complete", count: 0, disc: "done" },
];
const RETURN_COLUMNS: readonly BoardLayoutColumn[] = [
  { key: "preparing", label: "Preparing", count: 1, disc: "half" },
  { key: "in_review", label: "In review", count: 1, disc: "dot" },
  { key: "ready", label: "Ready", count: 1, disc: "done", accepts: false },
];
const LANES: readonly BoardLayoutLane[] = [
  { key: "a", title: "Area A", meta: "2 programs" },
  { key: "b", title: "Area B", meta: "1 program" },
];
const SLOTS = {
  p: { level: "L1", role: "Preparer", signer: null, at: null },
  r: { level: "L2", role: "Reviewer", signer: null, at: null },
};

function programs(state: T19State): BoardLayoutCard[] {
  const base = {
    owner: "CH",
    ownerName: "Cole Hart",
    metrics: [0, 0, 0, 0] as const,
    ...SLOTS,
  };
  const three: BoardLayoutCard = {
    ...base,
    id: "PRG-120",
    lane: "b",
    column: state === "c" ? "in_progress" : "not_started",
    version: 1,
    title: "Program three",
    code: "PRG-120",
    owner: "HL",
    ownerName: "Hannah Leclerc",
    ...(state === "c" ? { spin: true, agent: { state: "running" as const } } : {}),
    todos: "0 of 3",
    status: "Not started",
  };
  return [
    {
      ...base,
      id: "PRG-100",
      lane: "a",
      column: "in_progress",
      version: 1,
      title: "Program one",
      code: "PRG-100",
      todos: "1 of 3",
      status: "In progress",
    },
    {
      ...base,
      id: "PRG-110",
      lane: "a",
      column: "in_review",
      version: 1,
      title: "Program two",
      code: "PRG-110",
      todos: "3 of 3",
      status: "In review",
    },
    ...(state === "e" ? [] : [three]),
  ];
}

function viewOf(state: T19State): BoardView {
  if (state === "i") return "binder";
  return state === "j" ? "sheet" : "board";
}

export function t19Props(state: T19State): Omit<BoardLayoutProps, "onMoveIntent"> {
  const common = {
    label: "Programs",
    view: viewOf(state),
    filters: [
      { key: "agents", label: "Agents", icon: "atom" as const, options: [], value: null },
      { key: "phase", label: "Phase", options: [], value: null },
      { key: "area", label: "Audit area", icon: "layers" as const, options: [], value: null },
      {
        key: "owner",
        label: "Owner",
        icon: "user" as const,
        options: [{ value: "CH", label: "Cole Hart" }],
        value: state === "e" ? "CH" : null,
      },
    ],
    runOnMove: { allowed: true, on: state === "c" },
    navigator: {
      title: "Programs",
      items: [
        { key: "all", label: "All programs", count: 3 },
        { key: "a", label: "Area A", count: 2, depth: 1 as const },
        { key: "b", label: "Area B", count: 1, depth: 1 as const },
      ],
    },
    sheet: <p className="p-[12px] text-[12px] text-ink-3">T18 sheet over the same programs</p>,
  };
  switch (state) {
    case "f":
      return {
        ...common,
        variant: "audit",
        columns: AUDIT_COLUMNS.map((c) => ({ ...c, count: 0 })),
        lanes: [],
        cards: [],
        state: "empty",
      };
    case "g":
      return {
        ...common,
        variant: "audit",
        columns: AUDIT_COLUMNS,
        lanes: LANES,
        cards: [],
        state: "loading",
      };
    case "h":
      return {
        ...common,
        variant: "control",
        runOnMove: { allowed: false, on: false },
        navigator: { ...common.navigator, collapsed: true },
        columns: CONTROL_COLUMNS,
        lanes: [{ key: "cc6", title: "CC6 Logical access", meta: "3 controls" }],
        cards: [
          {
            id: "CC6.1",
            lane: "cc6",
            column: "not_started",
            version: 1,
            variant: "control",
            title: "Access is reviewed quarterly",
            code: "CC6.1",
            owner: "CH",
            ownerName: "Cole Hart",
            tag: "CC6.1",
            result: "none",
          },
          {
            id: "CC6.2",
            lane: "cc6",
            column: "testing",
            version: 1,
            variant: "control",
            title: "New access is approved",
            code: "CC6.2",
            owner: "CH",
            ownerName: "Cole Hart",
            tag: "CC6.2",
            result: "none",
          },
          {
            id: "CC6.3",
            lane: "cc6",
            column: "preparer_review",
            version: 1,
            variant: "control",
            title: "Access is removed on exit",
            code: "CC6.3",
            owner: "HL",
            ownerName: "Hannah Leclerc",
            tag: "CC6.3",
            result: "exc",
          },
        ],
      };
    case "k":
      return {
        ...common,
        variant: "returns",
        navigator: undefined as never,
        columns: RETURN_COLUMNS,
        lanes: [{ key: "ty", title: "TY2025", meta: "3 returns" }],
        cards: [
          {
            id: "R1",
            lane: "ty",
            column: "preparing",
            version: 1,
            variant: "return",
            title: "Client one",
            code: "1065",
            owner: "CH",
            ownerName: "Cole Hart",
            sub: "Form 1065",
            pill: "Preparing",
            due: "Due Mar 16",
          },
          {
            id: "R2",
            lane: "ty",
            column: "in_review",
            version: 1,
            variant: "return",
            title: "Client two",
            code: "1120-S",
            owner: "HL",
            ownerName: "Hannah Leclerc",
            sub: "Form 1120-S",
            pill: "In review",
            due: "Due Mar 16",
          },
          {
            id: "R3",
            lane: "ty",
            column: "ready",
            version: 1,
            variant: "return",
            title: "Client three",
            code: "1040",
            owner: "CH",
            ownerName: "Cole Hart",
            sub: "Form 1040",
            pill: "Ready",
            due: "Due Apr 15",
          },
        ],
      };
    case "l":
      return {
        ...common,
        variant: "close",
        navigator: undefined as never,
        columns: AUDIT_COLUMNS.map((c) =>
          c.key === "complete"
            ? { ...c, count: 1 }
            : c.key === "in_progress"
              ? { ...c, count: 1 }
              : { ...c, count: 0 },
        ),
        lanes: [
          { key: "ga", title: "Group A", meta: "1 group" },
          { key: "gb", title: "Group B", meta: "1 group", done: "1 of 1", collapsed: true },
        ],
        cards: [
          {
            id: "G1",
            lane: "ga",
            column: "in_progress",
            version: 1,
            variant: "close",
            title: "Group A tasks",
            code: "GRP-A",
            owner: "CH",
            ownerName: "Cole Hart",
            done: { text: "2 of 3" },
          },
          {
            id: "G2",
            lane: "gb",
            column: "complete",
            version: 1,
            variant: "close",
            title: "Group B tasks",
            code: "GRP-B",
            owner: "HL",
            ownerName: "Hannah Leclerc",
            done: { text: "1 of 1", complete: true },
          },
        ],
      };
    default:
      return {
        ...common,
        variant: "audit",
        columns: AUDIT_COLUMNS,
        lanes: LANES,
        cards: programs(state),
        ...(state === "b" ? { forceDrag: { cardId: "PRG-120", over: "in_progress" } } : {}),
      };
  }
}

export function T19Board({ state }: { state: T19State }): JSX.Element {
  const props = t19Props(state);
  const [on, setOn] = useState(props.runOnMove.on);
  return (
    <div className="flex h-[640px] w-[1376px] flex-col bg-shell" data-t19={state}>
      <BoardLayout
        {...props}
        runOnMove={{ ...props.runOnMove, on }}
        onRunOnMove={setOn}
        onMoveIntent={(intent) =>
          Promise.resolve(
            intent.toColumn === "complete" ||
              intent.toColumn === "review_complete" ||
              intent.toColumn === "ready"
              ? {
                  kind: "guarded",
                  requires: "sign_off",
                  text: "Moving to Complete needs a reviewer sign-off.",
                }
              : intent.runAgent
                ? {
                    kind: "dispatched",
                    runId: "run",
                    text: "Program moved to In progress · run started · logged in Activity",
                  }
                : { kind: "moved" },
          )
        }
      />
    </div>
  );
}

export function T19Specimen(): JSX.Element {
  return (
    <Sheet title="T19 Board" meta="a–l · placeholder content (TPL-21 is the seeded specimen)">
      {T19_STATES.map((s) => (
        <T19Board key={s} state={s} />
      ))}
    </Sheet>
  );
}
