// SHL-17 To-do drawer and My to-dos (P-05-T13; handoff SHL-17) on C-30 ToDoRow, ToDoGroup and
// DueChip, one artboard at a time from the collaboration seed (P-05-T03): a Margaret's view, b New
// to-do (Create stays disabled until a title and an assignee are set), c assigned to Marcus, d
// overdue, e done, f My to-dos. Writes go to the host (POST /v1/todos, /complete, /reopen); the
// drawer never moves a status itself. Marking done shows "To-do done · Undo" for 4 s, and Undo
// calls only the host's reopen (P-05 §4: an undo is a reopen, never a delete).
import type { PersonCandidateOut, TodoOut } from "@abacus/api-client";
import { Button, Pill } from "@abacus/ui";
import { type JSX, useState } from "react";
import { DueChip, Ring, ToDoGroup, ToDoRow } from "../../domain/collaboration";
import { NORTHWIND_TEAM, myTodos, todoFor } from "../../fixtures/scenarios/SHL-17";
import { COPY } from "./copy";
import type { State } from "./scenarios";

export { STATES, type State } from "./scenarios";

/** Each artboard's business date (the seed's clocks). */
const TODAY: Record<State, string> = {
  a: "2026-09-14",
  b: "2026-09-14",
  c: "2026-09-14",
  d: "2026-09-21",
  e: "2026-09-28",
  f: "2026-09-14",
};

export interface TodoDrawerProps {
  state: State;
  /** POST /v1/todos: the title and the assignee picked (never the agent). */
  onCreate?: (title: string, assigneeId: string) => void;
  /** POST /v1/todos/{id}/complete. */
  onComplete?: (id: string) => void;
  /** POST /v1/todos/{id}/reopen: Reopen, and the Undo toast. */
  onReopen?: (id: string) => void;
  onOpenTodo?: (id: string) => void;
  onReassign?: (id: string) => void;
}

function NewTodo({ onCreate }: { onCreate?: TodoDrawerProps["onCreate"] }): JSX.Element {
  const [title, setTitle] = useState("");
  const [assignee, setAssignee] = useState<PersonCandidateOut | null>(null);
  const ready = title.trim() !== "" && assignee !== null;
  return (
    <div className="flex flex-col gap-[10px] p-[12px]">
      <input
        aria-label={COPY.titlePlaceholder}
        placeholder={COPY.titlePlaceholder}
        value={title}
        onChange={(e) => {
          setTitle(e.target.value);
        }}
        className="rounded-[10px] bg-card px-[14px] py-[12px] text-[15px] shadow-e1 outline-none"
      />
      <span className="text-[12px] text-ink-2">Northwind · Exceptions row 6</span>
      <div
        role="listbox"
        aria-label={COPY.pickerLabel}
        className="rounded-[10px] bg-card shadow-e1"
      >
        <div className="px-[10px] py-[6px] text-[11px] font-medium text-ink-3">
          {COPY.pickerLabel}
        </div>
        {NORTHWIND_TEAM.map((p) => (
          <button
            key={p.user_id}
            type="button"
            role="option"
            aria-selected={assignee?.user_id === p.user_id}
            onClick={() => {
              setAssignee(p);
            }}
            className={`flex h-[32px] w-full items-center gap-[8px] px-[10px] text-left text-[13px] ${assignee?.user_id === p.user_id ? "bg-nested" : ""}`}
          >
            <span className="flex size-[20px] items-center justify-center rounded-full bg-chip text-[10.5px] font-medium text-ink-2">
              {p.initials}
            </span>
            {p.is_self ? `${p.name} (you)` : `${p.name}${p.title ? ` · ${p.title}` : ""}`}
          </button>
        ))}
        <div className="px-[10px] py-[6px] text-[11px] text-ink-3">{COPY.pickerFooter}</div>
      </div>
      <Button
        variant="primary"
        disabled={!ready}
        title={ready ? undefined : COPY.createNeeds}
        onClick={() => {
          if (ready) onCreate?.(title.trim(), assignee.user_id);
        }}
      >
        {COPY.create}
      </Button>
    </div>
  );
}

function TodoDetail({
  state,
  todo,
  onComplete,
  onReopen,
  onReassign,
}: {
  state: State;
  todo: TodoOut;
  onComplete?: TodoDrawerProps["onComplete"];
  onReopen?: TodoDrawerProps["onReopen"];
  onReassign?: TodoDrawerProps["onReassign"];
}): JSX.Element {
  const [toast, setToast] = useState(false);
  const done = todo.status === "done";
  const today = TODAY[state];
  const checked = (todo.checklist ?? []).filter((i) => i.done).length;
  const complete = (): void => {
    onComplete?.(todo.id);
    setToast(true);
  };
  return (
    <div className="flex flex-col gap-[10px] p-[12px]">
      {state === "c" ? (
        <div
          data-banner
          className="rounded-[10px] bg-card px-[12px] py-[8px] text-[12.5px] text-ink-2 shadow-e1"
        >
          {COPY.assignedBanner(todo.created_by.name, "12:36 PM")}
        </div>
      ) : null}
      <div className="rounded-[12px] bg-card px-[14px] py-[12px] shadow-e1">
        <div className="flex items-start gap-[8px]">
          <Ring
            done={done}
            label={done ? COPY.reopen : COPY.markDone}
            onToggle={done ? () => onReopen?.(todo.id) : complete}
          />
          <h2 className={`text-[15px] font-medium leading-[1.3] ${done ? "text-ink-2" : ""}`}>
            {todo.title}
          </h2>
        </div>
        <div className="mt-[8px] flex flex-wrap gap-[6px]">
          <Pill variant={done ? "green-tint" : "neutral"}>{done ? COPY.done : COPY.open}</Pill>
          {todo.due_on ? <DueChip dueOn={todo.due_on} today={today} done={done} /> : null}
          {todo.anchor ? (
            <span
              data-linked
              className="rounded-[6px] bg-nested px-[6px] text-[11.5px] text-ink-2"
            >
              {todo.anchor.label}
            </span>
          ) : null}
        </div>
      </div>
      <section aria-label={COPY.details} className="rounded-[10px] bg-card shadow-e1">
        <div className="flex h-[33px] items-center bg-band-hd px-[12px] text-[13.5px] font-medium">
          {COPY.details}
        </div>
        <dl className="flex flex-col">
          <div className="flex h-[34px] items-center justify-between px-[12px]">
            <dt className="text-ink-2">{COPY.assignee}</dt>
            <dd className="font-medium">{todo.assignee.name}</dd>
          </div>
        </dl>
        {/* The row's text sits between the two pairs; a <dl> holds only <dt>/<dd> groups. */}
        {todo.row_text ? (
          <p className="px-[12px] py-[8px] text-[12.5px] leading-[1.5] text-ink-2">
            {todo.row_text}
          </p>
        ) : null}
        <dl className="flex flex-col">
          <div className="flex h-[34px] items-center justify-between px-[12px]">
            <dt className="text-ink-2">{COPY.created}</dt>
            <dd className="font-medium">{todo.created_by.name}</dd>
          </div>
        </dl>
      </section>
      {(todo.checklist ?? []).length > 0 ? (
        <section aria-label={COPY.checklist} className="rounded-[10px] bg-card shadow-e1">
          <div className="flex h-[33px] items-center justify-between bg-band-hd px-[12px] text-[13.5px] font-medium">
            {COPY.checklist}
            <span className="text-[12px] font-normal text-ink-3">{`${String(checked)} of ${String(todo.checklist?.length ?? 0)}`}</span>
          </div>
          <ul>
            {(todo.checklist ?? []).map((i) => (
              <li
                key={i.id}
                data-check-item
                className="flex h-[34px] items-center gap-[8px] px-[12px] text-[12.5px]"
              >
                <Ring done={i.done} label={i.text} />
                {i.text}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {done ? <p className="text-[12.5px] text-green-ink">{COPY.doneLine}</p> : null}
      {state === "a" ? (
        <p className="px-[4px] text-[11.5px] text-ink-3">{COPY.activityA}</p>
      ) : null}
      <footer className="flex gap-[8px]">
        {done ? (
          <Button variant="secondary" onClick={() => onReopen?.(todo.id)}>
            {COPY.reopen}
          </Button>
        ) : (
          <>
            <Button variant="primary" onClick={complete}>
              {COPY.markDone}
            </Button>
            {state === "c" ? (
              <Button variant="secondary" onClick={() => onReassign?.(todo.id)}>
                {COPY.reassign}
              </Button>
            ) : null}
          </>
        )}
      </footer>
      {toast ? (
        <div
          role="status"
          className="flex items-center gap-[8px] rounded-[10px] bg-espresso px-[12px] py-[8px] text-[12.5px] text-on-dark"
        >
          {COPY.toastDone}
          <button
            type="button"
            className="font-medium underline"
            onClick={() => {
              setToast(false);
              onReopen?.(todo.id);
            }}
          >
            {COPY.undo}
          </button>
        </div>
      ) : null}
    </div>
  );
}

function MyTodos({
  onOpenTodo,
  onComplete,
}: Pick<TodoDrawerProps, "onOpenTodo" | "onComplete">): JSX.Element {
  const page = myTodos();
  const bucket = (b: string) => page.items.filter((t) => t.bucket === b);
  const groups = [
    { title: COPY.overdue, key: "overdue", tone: "overdue" as const },
    { title: COPY.today, key: "today", tone: "neutral" as const },
    { title: COPY.thisWeek, key: "this_week", tone: "neutral" as const },
  ];
  return (
    <div className="flex flex-col">
      <div className="flex gap-[4px] px-[12px] py-[6px] text-[12px]">
        <span className="rounded-[6px] bg-card px-[8px] font-medium shadow-e1">
          {COPY.segmentOpen(page.counts?.open ?? 0)}
        </span>
        <span className="px-[8px] text-ink-2">{COPY.segmentDone}</span>
      </div>
      {groups.map((g) => {
        const rows = bucket(g.key);
        return rows.length ? (
          <ToDoGroup key={g.key} title={g.title} count={rows.length} tone={g.tone}>
            {rows.map((t) => (
              <ToDoRow
                key={t.id}
                todo={t}
                today={TODAY.f}
                {...(onOpenTodo ? { onOpen: onOpenTodo } : {})}
                {...(onComplete ? { onToggle: onComplete } : {})}
              />
            ))}
          </ToDoGroup>
        ) : null;
      })}
      <p className="px-[12px] py-[8px] text-[11.5px] text-ink-3">{`${String(page.counts?.open ?? 0)} open · Northwind PY2025`}</p>
    </div>
  );
}

export function TodoDrawer({
  state,
  onCreate,
  onComplete,
  onReopen,
  onOpenTodo,
  onReassign,
}: TodoDrawerProps): JSX.Element {
  const todo = todoFor(state);
  const title = state === "b" ? COPY.newTodo : state === "f" ? COPY.myTodos : COPY.todo;
  return (
    <aside
      data-screen="SHL-17"
      data-state={state}
      aria-label={title}
      className="flex w-[480px] flex-col bg-shell"
    >
      <header className="flex h-[46px] items-center px-[14px] text-[14.5px] font-medium">
        {title}
      </header>
      {state === "b" ? <NewTodo {...(onCreate ? { onCreate } : {})} /> : null}
      {state === "f" ? (
        <MyTodos {...(onOpenTodo ? { onOpenTodo } : {})} {...(onComplete ? { onComplete } : {})} />
      ) : null}
      {todo && state !== "b" && state !== "f" ? (
        <TodoDetail
          state={state}
          todo={todo}
          {...(onComplete ? { onComplete } : {})}
          {...(onReopen ? { onReopen } : {})}
          {...(onReassign ? { onReassign } : {})}
        />
      ) : null}
    </aside>
  );
}
