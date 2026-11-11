// C-30 ToDoRow, ToDoGroup and DueChip (P-05-T13; handoff SHL-17, addendum pack 15). The due chip's
// words come from the due date and the viewer's business date (overdue is derived, never stored):
// "Wed Sep 16 · 2 days" (nested), "Today" (amber-tint), "Overdue · Sep 18" (red-tint), "Due Sep 28"
// once the to-do is done. A row opens its to-do; its ring marks it done through the host.
import type { TodoOut } from "@abacus/api-client";
import { cn, date } from "@abacus/ui";
import type { JSX, ReactNode } from "react";

const DAY = 86_400_000;
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;

function utc(isoDate: string): Date {
  return new Date(`${isoDate}T00:00:00Z`);
}

export interface DueWords {
  text: string;
  tone: "nested" | "today" | "overdue";
}

/** The chip's words for `due_on` seen on `today` (both ISO dates, the firm's business date). */
export function dueWords(dueOn: string, today: string, done = false, compact = false): DueWords {
  const due = utc(dueOn);
  // The due date is a calendar date: format it in UTC so the day never shifts (format.ts).
  const label = date(dueOn, { now: utc(today), tz: "UTC" });
  if (done) return { text: `Due ${label}`, tone: "nested" };
  const days = Math.round((due.getTime() - utc(today).getTime()) / DAY);
  if (days < 0) return { text: `Overdue · ${label}`, tone: "overdue" };
  if (days === 0) return { text: "Today", tone: "today" };
  if (compact) return { text: label, tone: "nested" }; // My to-dos rows: "Sep 16"
  const weekday = WEEKDAYS[due.getUTCDay()] ?? "";
  return {
    text: `${weekday} ${label} · ${String(days)} day${days === 1 ? "" : "s"}`,
    tone: "nested",
  };
}

export function DueChip({
  dueOn,
  today,
  done = false,
  compact = false,
}: {
  dueOn: string;
  today: string;
  done?: boolean;
  compact?: boolean;
}): JSX.Element {
  const words = dueWords(dueOn, today, done, compact);
  return (
    <span
      data-due={words.tone}
      className={cn(
        "inline-flex h-[22px] items-center gap-[4px] rounded-[6px] px-[6px] text-[11.5px]",
        words.tone === "overdue"
          ? "bg-red-tint text-red-ink"
          : words.tone === "today"
            ? "bg-amber-tint text-amber-ink"
            : "bg-nested text-ink-2",
      )}
    >
      <span aria-hidden className="text-ink-3">
        ▦
      </span>
      {words.text}
    </span>
  );
}

export function Ring({
  done,
  onToggle,
  label,
}: {
  done: boolean;
  onToggle?: () => void;
  label: string;
}): JSX.Element {
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={done}
      onClick={onToggle}
      className={cn(
        "flex size-[15px] shrink-0 items-center justify-center rounded-full text-[9px]",
        done ? "bg-green text-on-dark" : "inset-ring-[1.3px] inset-ring-stroke",
      )}
    >
      {done ? "✓" : null}
    </button>
  );
}

export function ToDoRow({
  todo,
  today,
  onOpen,
  onToggle,
}: {
  todo: TodoOut;
  today: string;
  onOpen?: (id: string) => void;
  onToggle?: (id: string) => void;
}): JSX.Element {
  const done = todo.status === "done";
  return (
    <li
      data-todo={todo.id}
      className="flex h-[52px] items-center gap-[8px] border-b-[0.5px] border-hair px-[12px]"
    >
      <Ring
        done={done}
        label={done ? `Reopen ${todo.title}` : `Mark done ${todo.title}`}
        onToggle={() => onToggle?.(todo.id)}
      />
      <button
        type="button"
        className="flex min-w-0 flex-1 flex-col text-left"
        onClick={() => onOpen?.(todo.id)}
      >
        <span className={cn("truncate text-[13px]", done && "text-ink-2")}>{todo.title}</span>
        <span className="truncate text-[11.5px] text-ink-3">
          from {todo.created_by.initials}
          {todo.anchor ? ` · ${todo.anchor.label}` : ""}
        </span>
      </button>
      {todo.unread ? (
        <span aria-label="Unread" className="size-[7px] rounded-full bg-red" />
      ) : null}
      {todo.due_on ? <DueChip dueOn={todo.due_on} today={today} done={done} compact /> : null}
    </li>
  );
}

export function ToDoGroup({
  title,
  count,
  tone = "neutral",
  children,
}: {
  title: string;
  count: number;
  tone?: "neutral" | "overdue";
  children: ReactNode;
}): JSX.Element {
  return (
    <section data-todo-group={title} aria-label={title}>
      <div className="flex h-[31px] items-center gap-[6px] bg-band-hd px-[12px] text-[13.5px] font-medium">
        {title}
        <span
          className={cn(
            "rounded-[6px] px-[5px] text-[11.5px]",
            tone === "overdue" ? "bg-red-tint text-red-ink" : "bg-chip text-ink-2",
          )}
        >
          {count}
        </span>
      </div>
      <ul>{children}</ul>
    </section>
  );
}
