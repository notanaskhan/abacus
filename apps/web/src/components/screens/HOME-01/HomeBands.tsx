// HOME-01 R2 (I-01-T24): the "Waiting on you" bands that follow "Approvals & sends": To-dos (C-30
// rows: ring, title, from-person, linked-object chip, due chip) and Mentions (AtSign chip, "<person>
// mentioned you", the quoted text in 11.5 ink-3 and the object). Same 31 px band and 44 px row
// grammar as the built bands. Built as new, unwired components on P-05's My to-dos (`TodoOut`) and
// mentions (the C16 feed's `mention` items: `actor_name`, `excerpt`, `object_label` facts, resolved at
// read time) so the live HOME-01 composition is untouched inside the
// Jan 1 - Apr 20, 2028 window (P-29 rule 2). Neither band counts into the header's number.
import type { NotificationItemOut, TodoOut } from "@abacus/api-client";
import { Icon } from "@abacus/ui";
import type { JSX } from "react";
import { BAND_COPY } from "./copy";

export interface HomeBandsProps {
  todos: readonly TodoOut[];
  mentions: readonly NotificationItemOut[];
  /** "Mon Sep 16"-style due chips and "12:35 PM" times come from the host's clock helpers. */
  dueLabel: (iso: string) => string;
  timeLabel: (iso: string) => string;
  /** A to-do row opens SHL-17 on it. */
  onOpenTodo?: (todo: TodoOut) => void;
  /** A mention row opens SHL-18 on its object's thread. */
  onOpenMention?: (mention: NotificationItemOut) => void;
}

function Band({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: JSX.Element;
}): JSX.Element {
  return (
    <section aria-label={title} data-home-band={title}>
      <h3 className="-mt-[0.5px] flex h-[31px] items-center gap-[8px] bg-band-hd px-[14px] text-body font-medium hairline-t hairline-b">
        <span className="min-w-0 flex-1 truncate">{title}</span>
        <span className="text-dense font-normal text-ink-3 tabular-nums">{count}</span>
      </h3>
      {children}
    </section>
  );
}

function Empty({ text }: { text: string }): JSX.Element {
  return (
    <p className="flex h-[44px] items-center px-[14px] text-[12px] text-ink-3 hairline-b">
      {text}
    </p>
  );
}

function fact(item: NotificationItemOut, key: string): string {
  const value = item.facts[key];
  return typeof value === "string" ? value : "";
}

export function TodosBand({
  todos,
  dueLabel,
  onOpenTodo,
}: Pick<HomeBandsProps, "todos" | "dueLabel" | "onOpenTodo">): JSX.Element {
  return (
    <Band title={BAND_COPY.todos.title} count={todos.length}>
      {todos.length === 0 ? (
        <Empty text={BAND_COPY.todos.empty} />
      ) : (
        <ul>
          {todos.map((todo) => (
            <li key={todo.id} className="hairline-b">
              <button
                type="button"
                data-todo={todo.id}
                onClick={() => onOpenTodo?.(todo)}
                className="flex h-[44px] w-full items-center gap-[10px] px-[14px] text-left"
              >
                <span
                  aria-hidden
                  className="size-[14px] shrink-0 rounded-full inset-ring-1 inset-ring-ink-3"
                />
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-body">{todo.title}</span>
                  <span className="truncate text-[11.5px] text-ink-3">
                    {BAND_COPY.todos.from(todo.created_by.name)}
                  </span>
                </span>
                {todo.anchor ? (
                  <span
                    data-chip="object"
                    className="shrink-0 rounded-[5px] bg-chip px-[6px] text-[11.5px] text-ink-2"
                  >
                    {todo.anchor.label}
                  </span>
                ) : null}
                {todo.due_on ? (
                  <span
                    data-chip="due"
                    className={`shrink-0 rounded-[5px] px-[6px] text-[11.5px] ${todo.overdue ? "bg-red-tint text-red-ink" : "bg-nested text-ink-2"}`}
                  >
                    {dueLabel(todo.due_on)}
                  </span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      )}
    </Band>
  );
}

export function MentionsBand({
  mentions,
  timeLabel,
  onOpenMention,
}: Pick<HomeBandsProps, "mentions" | "timeLabel" | "onOpenMention">): JSX.Element {
  return (
    <Band title={BAND_COPY.mentions.title} count={mentions.length}>
      {mentions.length === 0 ? (
        <Empty text={BAND_COPY.mentions.empty} />
      ) : (
        <ul>
          {mentions.map((m) => (
            <li key={m.id} className="hairline-b">
              <button
                type="button"
                data-mention={m.id}
                data-read={m.read}
                onClick={() => onOpenMention?.(m)}
                className="flex min-h-[44px] w-full items-center gap-[10px] px-[14px] py-[6px] text-left"
              >
                <span
                  aria-hidden
                  className="flex size-[22px] shrink-0 items-center justify-center rounded-[6px] bg-chip text-ink-2"
                >
                  <Icon name="at-sign" size={13} />
                </span>
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-body">
                    {BAND_COPY.mentions.mentioned(fact(m, "actor_name"))}
                  </span>
                  <span className="truncate text-[11.5px] text-ink-3">
                    {BAND_COPY.mentions.quoted(fact(m, "excerpt"), fact(m, "object_label"))}
                  </span>
                </span>
                <span className="shrink-0 text-[11.5px] text-ink-3 tabular-nums">
                  {timeLabel(m.created_at)}
                </span>
                {m.read ? null : (
                  <span
                    aria-label={BAND_COPY.mentions.unread}
                    data-unread
                    className="size-[6px] shrink-0 rounded-full bg-ink"
                  />
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </Band>
  );
}

/** Both bands, in order, after "Approvals & sends" (the host places them; the header count is
 * the host's, unchanged: to-dos and mentions never count into it). */
export function HomeBands(props: HomeBandsProps): JSX.Element {
  return (
    <div data-home="r2-bands">
      <TodosBand
        todos={props.todos}
        dueLabel={props.dueLabel}
        {...(props.onOpenTodo ? { onOpenTodo: props.onOpenTodo } : {})}
      />
      <MentionsBand
        mentions={props.mentions}
        timeLabel={props.timeLabel}
        {...(props.onOpenMention ? { onOpenMention: props.onOpenMention } : {})}
      />
    </div>
  );
}
