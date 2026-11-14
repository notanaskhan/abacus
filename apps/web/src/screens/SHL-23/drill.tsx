// SHL-23 2, 3 and History (I-02-T17; docs/screens/SHL-23.md; SPEC-654 §3.5–§3.8; DEC-4938): the
// drill-in (‹ Today, the briefing's narrative or its code fallback, the blocker cards, Waiting
// downstream, Assign open items, Open return ›), the SHL-17 prefill sheet (one prefill at a time;
// the person presses Create, INV-1, INV-5; a reserved item reads "Reserved to you — not
// assignable"), the History list and a past brief's read-only header, and the ask thread (the
// person's bubble and the cited answer card from the Today session's items; a request to act
// reads the read-only notice pointing to SHL-12). Nothing here counts or composes a figure.
import type {
  AssignPrefill,
  DrillVm,
  HistoryPage,
  SessionItemOut,
} from "@abacus/api-client";
import {
  type AgentBlocksPayload,
  type AgentBlocksProps,
  AgentBlocks,
  Button,
  EmptyState,
  Icon,
} from "@abacus/ui";
import type { JSX } from "react";
import { CELL_LABELS, COPY } from "./copy";

const STATE_WORDS: Readonly<Record<string, string>> = {
  blocked: "Blocked",
  blocked_on_decision: "Blocked on decision",
  fix_proposed: "Blocked",
};

export interface TodayDrillProps {
  drill: DrillVm;
  onBack: () => void;
  onOpen?: ((href: string) => void) | undefined;
  onAssign?: (() => void) | undefined;
  onHighlight?: ((refs: readonly string[] | null) => void) | undefined;
}

export function TodayDrill({
  drill,
  onBack,
  onOpen,
  onAssign,
  onHighlight,
}: TodayDrillProps): JSX.Element {
  const summary = (drill.summary_blocks ?? []) as unknown as AgentBlocksPayload[];
  const reserved = new Set((drill.not_assignable ?? []).map((n) => n.gate_id));
  return (
    <div
      data-screen="SHL-23"
      data-state="drill"
      className="flex min-h-0 flex-1 flex-col"
      onMouseEnter={() => onHighlight?.(drill.select_refs ?? [])}
      onMouseLeave={() => onHighlight?.(null)}
    >
      <header className="flex h-[46px] flex-none items-center gap-[6px] px-[12px]">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <Icon name="chevron-left" size={12} />
          {COPY.back}
        </Button>
        <span className="min-w-0 flex-1 truncate text-[14px] font-medium text-ink">
          {drill.title}
        </span>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto px-[12px] pb-[12px]">
        <div className="text-[12.5px] text-ink-2">
          {summary.length > 0 ? (
            summary.map((doc, i) => <AgentBlocks key={String(i)} blocks={doc} facts={{}} />)
          ) : (
            <p>{drill.summary_fallback ?? COPY.summaryUnavailable}</p>
          )}
        </div>
        <ul className="mt-[10px] flex flex-col gap-[8px]">
          {drill.blockers.map((row) => {
            const why = (row.why_blocks ?? []) as unknown as AgentBlocksPayload[];
            return (
              <li
                key={row.gate_id}
                data-blocker={row.gate_id}
                className="rounded-[10px] bg-card p-[10px] shadow-e1"
              >
                <span className="flex items-center gap-[6px]">
                  <span className="flex-1 text-[13px] font-medium text-ink">{row.title}</span>
                  {row.state && STATE_WORDS[row.state] ? (
                    <span className="rounded-pill bg-amber-tint px-[6px] text-[11px] text-amber-ink">
                      {STATE_WORDS[row.state]}
                    </span>
                  ) : null}
                </span>
                <div className="text-[12px] text-ink-2">
                  {why.length > 0 ? (
                    why.map((doc, i) => <AgentBlocks key={String(i)} blocks={doc} facts={{}} />)
                  ) : (
                    <p>{row.context_line}</p>
                  )}
                </div>
                {reserved.has(row.gate_id) ? (
                  <p data-reserved className="mt-[4px] text-[11.5px] text-ink-3">
                    {COPY.reservedToYou}
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
        {(drill.downstream ?? []).length > 0 ? (
          <section className="mt-[10px]">
            <h3 className="text-[11.5px] text-ink-3">{COPY.waitingDownstream}</h3>
            <ul className="mt-[4px] flex flex-col">
              {(drill.downstream ?? []).map((d) => (
                <li key={d.work_item_id}>
                  <button
                    type="button"
                    onClick={() => onOpen?.(d.deep_link)}
                    className="flex w-full items-center gap-[6px] rounded-[8px] px-[6px] py-[4px] text-left text-[12px] text-ink-2 hover:bg-nested"
                  >
                    <span className="flex-1 truncate">{d.title}</span>
                    <span className="text-ink-3">{d.state_line}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        <div className="mt-[12px] flex gap-[6px]">
          {(drill.prefills ?? []).length > 0 ? (
            <Button variant="secondary" size="sm" icon="user-plus" onClick={onAssign}>
              {COPY.assign}
            </Button>
          ) : null}
          {drill.open_href ? (
            <Button variant="primary" size="sm" onClick={() => onOpen?.(drill.open_href)}>
              {COPY.openReturn}
              <Icon name="chevron-right" size={12} />
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export interface AssignSheetProps {
  prefill: AssignPrefill;
  position: number;
  of: number;
  creating?: boolean;
  onCreate: (p: AssignPrefill) => void;
  onSkip: () => void;
  onCancel: () => void;
}

/** SHL-17's new to-do, prefilled: the words are the server's; the person presses Create. */
export function AssignSheet({
  prefill,
  position,
  of,
  creating,
  onCreate,
  onSkip,
  onCancel,
}: AssignSheetProps): JSX.Element {
  return (
    <div
      role="dialog"
      aria-label={COPY.newTodo}
      data-screen="SHL-17"
      data-state="b"
      className="flex flex-col gap-[8px] rounded-[12px] bg-card p-[12px] shadow-e2"
    >
      <span className="flex items-center text-[12px] text-ink-3">
        <span className="flex-1 font-medium text-ink">{COPY.newTodo}</span>
        {of > 1 ? COPY.assignOf(position + 1, of) : null}
      </span>
      <p className="text-[14px] font-medium text-ink">{prefill.title}</p>
      <dl className="grid grid-cols-[72px_1fr] gap-y-[4px] text-[12px]">
        <dt className="text-ink-3">{COPY.assignee}</dt>
        <dd className="text-ink">{prefill.assignee_name}</dd>
        <dt className="text-ink-3">{COPY.due}</dt>
        <dd className="text-ink tabular-nums">{prefill.due_on}</dd>
      </dl>
      <span className="text-[12px] text-ink-2">{prefill.anchor_label}</span>
      <div className="flex justify-end gap-[6px]">
        <Button variant="ghost" size="sm" onClick={onCancel}>
          {COPY.cancel}
        </Button>
        {of > 1 ? (
          <Button variant="secondary" size="sm" onClick={onSkip}>
            {COPY.skip}
          </Button>
        ) : null}
        <Button
          variant="primary"
          size="sm"
          disabled={creating === true}
          onClick={() => {
            onCreate(prefill);
          }}
        >
          {COPY.create}
        </Button>
      </div>
    </div>
  );
}

export function TodayHistory({
  page,
  onBack,
  onPick,
}: {
  page: HistoryPage | undefined;
  onBack: () => void;
  onPick: (briefId: string) => void;
}): JSX.Element {
  const items = page?.items ?? [];
  return (
    <div data-screen="SHL-23" data-state="history" className="flex min-h-0 flex-1 flex-col">
      <header className="flex h-[46px] flex-none items-center gap-[6px] px-[12px]">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <Icon name="chevron-left" size={12} />
          {COPY.back}
        </Button>
        <span className="flex-1 text-[14px] font-medium text-ink">{COPY.historyTitle}</span>
      </header>
      {items.length === 0 ? (
        <EmptyState title={COPY.noHistory} />
      ) : (
        <ul className="flex flex-col px-[12px]">
          {items.map((h) => (
            <li key={h.brief_id}>
              <button
                type="button"
                data-brief={h.brief_id}
                onClick={() => {
                  onPick(h.brief_id);
                }}
                className="flex w-full flex-col rounded-[8px] px-[8px] py-[6px] text-left hover:bg-nested"
              >
                <span className="text-[13px] font-medium text-ink tabular-nums">
                  {h.brief_date}
                </span>
                <span className="text-[12px] text-ink-2">
                  {Object.entries(h.counts)
                    .filter(([, n]) => n > 0)
                    .map(([k, n]) => `${String(n)} ${CELL_LABELS[k] ?? k}`)
                    .join(" · ")}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function bodyOf(item: SessionItemOut): string {
  const body = item.payload["body"];
  return typeof body === "string" ? body : "";
}

/** SHL-23 3: the person's bubbles and the agent's cited answer cards, in order. */
export function AskThread({
  items,
  pending,
  onOpen,
}: {
  items: readonly SessionItemOut[];
  pending: string | null;
  onOpen?: ((href: string) => void) | undefined;
}): JSX.Element | null {
  const shown = items.filter((i) => ["user_message", "agent_blocks", "notice"].includes(i.kind));
  if (shown.length === 0 && pending === null) return null;
  return (
    <section data-ask-thread className="mt-[10px] flex flex-col gap-[8px]">
      {shown.map((item) => {
        if (item.kind === "user_message") {
          return (
            <p
              key={item.id}
              data-bubble
              className="self-end rounded-[12px] bg-ink px-[10px] py-[6px] text-[12.5px] text-card"
            >
              {bodyOf(item)}
            </p>
          );
        }
        if (item.kind === "agent_blocks") {
          const blocks = item.payload["blocks"] as AgentBlocksPayload;
          const cites = item.payload["cites"] as AgentBlocksProps["cites"] | undefined;
          return (
            <div
              key={item.id}
              data-answer
              className="rounded-[10px] bg-card p-[10px] text-[12.5px] text-ink-2 shadow-e1"
            >
              <AgentBlocks blocks={blocks} facts={{}} {...(cites === undefined ? {} : { cites })} />
            </div>
          );
        }
        const code = item.payload["code"];
        if (code === "today_read_only") {
          return (
            <div key={item.id} data-notice="today_read_only" className="text-[12px] text-ink-2">
              <p>{COPY.readOnly}</p>
              <Button variant="ghost" size="sm" onClick={() => onOpen?.("/home/approvals?band=sign_off")}>
                {COPY.openSignOff}
              </Button>
            </div>
          );
        }
        if (code === "nothing_written") return null;
        return (
          <p key={item.id} data-notice={String(code)} className="text-[12px] text-ink-3">
            {COPY.askFailed}
          </p>
        );
      })}
      {pending !== null ? (
        <>
          <p
            data-bubble
            className="self-end rounded-[12px] bg-ink px-[10px] py-[6px] text-[12.5px] text-card"
          >
            {pending}
          </p>
          <p className="text-[12px] text-ink-3">{COPY.thinking}</p>
        </>
      ) : null}
    </section>
  );
}
