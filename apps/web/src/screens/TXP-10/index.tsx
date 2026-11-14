// TXP-10 · Return › Issues (1065) (T-05-T58; docs/screens/TXP-10.md; handoff TXP-10 states A, A2,
// B, C, D, E, F; T9 `issues-entity`). The queue (Waiting on the client and Review points with the
// server's counts, search, Show resolved), the detail (assignee picker, severity, status, what it
// blocks, the workbook cells it blocks, why it was surfaced, the proposed fix to review in SHL-10,
// the client request with its POR-04 preview, Send reminder, Resolve with a note), the agent-fixing
// row and the empty states. Only a person approves, resolves or sends (INV-1); every count and
// figure is the server's.
import type {
  IssueDetailOut,
  WorkbookIssueAssigneeOptionOut,
  WorkbookReturnIssueOut,
  WorkbookReturnIssuesOut,
} from "@abacus/api-client";
import { AgentText, Button, EmptyState, Icon, Pill, Spinner, time as formatTime } from "@abacus/ui";
import { type JSX, useState } from "react";
import { COPY, SEVERITY, STATUS } from "./copy";

const OPEN = new Set(["open", "in_progress", "reopened"]);

export interface TXP10Props {
  queue: WorkbookReturnIssuesOut | undefined;
  selectedId: string | null;
  detail: IssueDetailOut | undefined;
  assignees?: readonly WorkbookIssueAssigneeOptionOut[];
  showResolved: boolean;
  query: string;
  onQuery?: (q: string) => void;
  onShowResolved?: (on: boolean) => void;
  onSelect?: (id: string) => void;
  /** A workbook cell opens TXP-11 on it (purple). */
  onOpenCell?: (sheet: string, range: string) => void;
  /** SHL-10 on the fix's proposal (Approve fix, Reject… with a reason, Edit…). */
  onReviewFix?: (proposalId: string) => void;
  /** SHL-15: the person's fix instructions on the issue. */
  onInstruct?: (issueId: string) => void;
  onAssign?: (issue: WorkbookReturnIssueOut, option: WorkbookIssueAssigneeOptionOut) => void;
  onSendToClient?: (issue: WorkbookReturnIssueOut) => void;
  onRemind?: (issue: WorkbookReturnIssueOut) => void;
  onResolve?: (issue: WorkbookReturnIssueOut, note: string) => void;
}

function Row({
  issue,
  selected,
  onSelect,
}: {
  issue: WorkbookReturnIssueOut;
  selected: boolean;
  onSelect?: ((id: string) => void) | undefined;
}): JSX.Element {
  const done = !OPEN.has(issue.status);
  return (
    <li>
      <button
        type="button"
        data-issue={issue.id}
        aria-pressed={selected}
        onClick={() => onSelect?.(issue.id)}
        className={`flex w-full items-start gap-[8px] px-[12px] pt-[8px] pb-[9px] text-left ${selected ? "bg-selected font-medium" : "hover:bg-nested"}`}
      >
        <span
          aria-hidden
          className={`mt-[3px] h-[13px] w-[13px] flex-none rounded-full border ${done ? "border-green bg-green" : "border-stroke"}`}
        />
        <span className="flex min-w-0 flex-1 flex-col">
          <span className={`line-clamp-2 text-[13px] leading-[1.32] ${done ? "text-ink-2" : "text-ink"}`}>
            {issue.title}
          </span>
          {issue.step ? <span className="text-[11.5px] text-ink-3">{issue.step}</span> : null}
        </span>
        {(issue.allowed_actions ?? []).includes("issue.fix") ? (
          <Icon name="settings" size={13} />
        ) : null}
      </button>
    </li>
  );
}

function Band({ title, children }: { title: string; children: React.ReactNode }): JSX.Element {
  return (
    <section className="border-t border-hair">
      <h3 className="flex h-[31px] items-center bg-band px-[14px] text-[13px] font-medium text-ink">
        {title}
      </h3>
      <div className="px-[14px] py-[8px]">{children}</div>
    </section>
  );
}

function Detail({
  issue,
  detail,
  assignees,
  onOpenCell,
  onReviewFix,
  onInstruct,
  onAssign,
  onSendToClient,
  onRemind,
  onResolve,
}: { issue: WorkbookReturnIssueOut; detail: IssueDetailOut | undefined } & Omit<
  TXP10Props,
  "queue" | "selectedId" | "detail" | "showResolved" | "query"
>): JSX.Element {
  const [resolving, setResolving] = useState(false);
  const [note, setNote] = useState("");
  const [picking, setPicking] = useState(false);
  const open = OPEN.has(issue.status);
  const fix = detail?.fix_run ?? null;
  const fixing = fix !== null && issue.status === "in_progress" && fix.status === "running";
  const waiting = issue.kind === "waiting_on_client";
  const resolvedBy = (detail?.events ?? []).filter((e) => e.event === "resolved").at(-1);
  return (
    <div data-detail={issue.id} className="flex min-h-0 flex-1 flex-col">
      <header className="flex h-[46px] flex-none items-center px-[14px]">
        <span className="flex-1 text-center text-[14.5px] font-medium text-ink">{COPY.issue}</span>
        {open ? (
          <Button variant="primary" size="sm" onClick={() => { setResolving(true); }}>
            {COPY.resolve}
          </Button>
        ) : null}
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <h2 className={`border-b border-hair px-[14px] py-[12px] text-[15px] leading-[1.3] font-medium ${open ? "text-ink" : "text-ink-2"}`}>
          {issue.title}
          {!open ? <Pill variant="green-tint">{COPY.resolved}</Pill> : null}
        </h2>
        <dl className="text-[13px]">
          <div className="flex h-[44px] items-center border-b border-hair px-[14px]">
            <dt className="w-[300px] text-ink-2">{COPY.assignedTo}</dt>
            <dd className="relative flex-1">
              <button
                type="button"
                disabled={!open}
                onClick={() => { setPicking(!picking); }}
                className="inline-flex items-center gap-[6px] text-ink"
              >
                {issue.assignee?.name ?? "—"}
                {open ? <Icon name="chevron-down" size={12} /> : null}
              </button>
              {picking ? (
                <ul role="listbox" aria-label={COPY.assignedTo} className="absolute z-10 mt-[4px] w-[260px] rounded-[10px] bg-card py-[4px] shadow-e2">
                  {(assignees ?? []).map((o) => (
                    <li key={`${o.kind}:${o.id ?? "agent"}`}>
                      <button
                        type="button"
                        role="option"
                        aria-selected={issue.assignee?.name === o.name}
                        onClick={() => {
                          setPicking(false);
                          onAssign?.(issue, o);
                        }}
                        className="flex w-full flex-col px-[10px] py-[6px] text-left hover:bg-nested"
                      >
                        <span className="text-[13px] text-ink">{o.name}</span>
                        {o.detail ? <span className="text-[11.5px] text-ink-3">{o.detail}</span> : null}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </dd>
          </div>
          <div className="flex h-[44px] items-center border-b border-hair px-[14px]">
            <dt className="w-[300px] text-ink-2">{COPY.severity}</dt>
            <dd className="flex-1 text-ink">{SEVERITY[issue.kind ?? ""] ?? issue.kind}</dd>
          </div>
          <div className="flex h-[44px] items-center border-b border-hair px-[14px]">
            <dt className="w-[300px] text-ink-2">{COPY.status}</dt>
            <dd data-status={issue.status} className="flex flex-1 items-center gap-[6px] text-ink">
              {fixing ? <Spinner label={COPY.agentFixing} size={10} /> : null}
              {!open && resolvedBy !== undefined
                ? COPY.resolvedBy(resolvedBy.actor_name, formatTime(resolvedBy.at))
                : (STATUS[issue.status] ?? issue.status)}
            </dd>
          </div>
        </dl>
        {detail?.internal_note ? (
          <Band title={COPY.whatItBlocks}>
            <p className="text-[12.5px] leading-[1.55] text-ink-2">{detail.internal_note}</p>
          </Band>
        ) : null}
        {(issue.cells ?? []).length > 0 ? (
          <Band title={COPY.workbookCells}>
            <ul className="flex flex-col">
              {(issue.cells ?? []).map((c) => (
                <li key={`${c.sheet}!${c.range}`}>
                  <button
                    type="button"
                    data-cell={`${c.sheet}!${c.range}`}
                    onClick={() => onOpenCell?.(c.sheet, c.range)}
                    className="flex h-[38px] w-full items-center gap-[8px] text-left text-[13px] text-ink hover:bg-nested"
                  >
                    <Icon name="table" size={14} />
                    <span className="flex-1">{`${c.sheet}!${c.range}`}</span>
                    <Icon name="chevron-right" size={12} />
                  </button>
                </li>
              ))}
            </ul>
          </Band>
        ) : null}
        {(detail?.explanations ?? []).length > 0 ? (
          <Band title={COPY.why}>
            {(detail?.explanations ?? []).map((x) => (
              <p key={x.id} className="text-[12.5px] leading-[1.55] text-ink-2">
                <AgentText text={x.text} />
              </p>
            ))}
          </Band>
        ) : null}
        {fix !== null ? (
          <Band title={COPY.proposedFix}>
            {fixing ? (
              <p data-agent-fixing className="flex items-center gap-[6px] text-[12.5px] text-ink-2">
                <Spinner label={fix.label} size={10} />
                {`${fix.label} · ${COPY.agentFixing}`}
              </p>
            ) : fix.proposal_id ? (
              <Button
                variant="primary"
                size="sm"
                icon="check"
                onClick={() => onReviewFix?.(fix.proposal_id ?? "")}
              >
                {COPY.reviewFix}
              </Button>
            ) : (
              <p className="text-[12.5px] text-ink-2">{fix.label}</p>
            )}
          </Band>
        ) : null}
        {waiting && detail?.client_wording ? (
          <Band title={COPY.clientRequest}>
            <div data-por04-preview className="rounded-[10px] bg-card p-[10px] text-[12.5px] text-ink shadow-e1">
              {detail.client_wording}
            </div>
            <div className="mt-[8px] flex gap-[6px]">
              {issue.request_item_id ? (
                <Button variant="secondary" size="sm" onClick={() => onRemind?.(issue)}>
                  {COPY.sendReminder}
                </Button>
              ) : (
                <Button variant="secondary" size="sm" onClick={() => onSendToClient?.(issue)}>
                  {COPY.sendToClient}
                </Button>
              )}
            </div>
          </Band>
        ) : null}
        {resolving ? (
          <div role="dialog" aria-label={COPY.noteLabel} className="m-[14px] rounded-[10px] bg-card p-[12px] shadow-e2">
            <label className="flex flex-col gap-[4px] text-[12px] text-ink-2">
              {COPY.noteLabel}
              <textarea
                value={note}
                placeholder={COPY.notePlaceholder}
                onChange={(e) => { setNote(e.target.value); }}
                className="min-h-[72px] rounded-[8px] bg-nested p-[8px] text-[12.5px] text-ink"
              />
            </label>
            <div className="mt-[8px] flex justify-end gap-[6px]">
              <Button variant="ghost" size="sm" onClick={() => { setResolving(false); }}>
                {COPY.cancel}
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  setResolving(false);
                  onResolve?.(issue, note.trim());
                }}
              >
                {COPY.confirmResolve}
              </Button>
            </div>
          </div>
        ) : null}
      </div>
      {open ? (
        <button
          type="button"
          onClick={() => onInstruct?.(issue.id)}
          className="m-[12px] flex h-[44px] flex-none items-center rounded-[12px] bg-nested px-[12px] text-left text-[13px] text-ink-3"
        >
          {COPY.composer}
        </button>
      ) : null}
    </div>
  );
}

export function TXP10(props: TXP10Props): JSX.Element {
  const { queue, selectedId, detail, showResolved, query, onQuery, onShowResolved, onSelect } = props;
  const items = queue?.items ?? [];
  const selected = items.find((i) => i.id === selectedId) ?? null;
  const sections = queue?.sections ?? [];
  const resolved = items.filter((i) => !OPEN.has(i.status));
  return (
    <div data-screen="TXP-10" data-badge={queue?.open_total ?? 0} className="flex min-h-0 flex-1 gap-[8px]">
      <aside aria-label={COPY.issues} className="flex w-[470px] flex-none flex-col rounded-[12px] bg-card shadow-e1">
        <header className="flex h-[46px] flex-none items-center gap-[6px] px-[10px]">
          <input
            aria-label={COPY.search}
            placeholder={COPY.search}
            value={query}
            onChange={(e) => onQuery?.(e.target.value)}
            className="h-[28px] w-[120px] rounded-[7px] bg-nested px-[8px] text-[12.5px]"
          />
          <span className="flex-1 text-center text-[14.5px] font-medium text-ink">{COPY.issues}</span>
          <Button variant="ghost" size="sm" onClick={() => onShowResolved?.(!showResolved)}>
            {showResolved ? COPY.hideResolved : COPY.showResolved}
          </Button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {(queue?.open_total ?? 0) === 0 && !showResolved ? (
            <EmptyState title={COPY.noOpen}>{COPY.noOpenBody}</EmptyState>
          ) : (
            sections.map((s) => (
              <section key={s.key} data-section={s.key}>
                <h3 className="flex h-[34px] items-center bg-band px-[12px] text-[14px] font-medium text-ink">
                  <span className="flex-1">{s.title}</span>
                  <span className="text-[12px] text-ink-3 tabular-nums">{s.count}</span>
                </h3>
                <ul>
                  {items
                    .filter((i) => i.section === s.key && OPEN.has(i.status))
                    .map((i) => (
                      <Row key={i.id} issue={i} selected={i.id === selectedId} onSelect={onSelect} />
                    ))}
                </ul>
              </section>
            ))
          )}
          {showResolved && resolved.length > 0 ? (
            <section data-section="resolved">
              <h3 className="flex h-[34px] items-center bg-band px-[12px] text-[14px] font-medium text-ink">
                <span className="flex-1">{COPY.resolved}</span>
                <span className="text-[12px] text-ink-3 tabular-nums">{queue?.resolved_total ?? resolved.length}</span>
              </h3>
              <ul>
                {resolved.map((i) => (
                  <Row key={i.id} issue={i} selected={i.id === selectedId} onSelect={onSelect} />
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      </aside>
      <main className="flex min-w-0 flex-1 flex-col rounded-[12px] bg-card shadow-e1">
        {selected === null ? (
          <EmptyState title={COPY.selectIssue}>{COPY.selectIssueBody}</EmptyState>
        ) : (
          <Detail {...props} issue={selected} detail={detail} />
        )}
      </main>
    </div>
  );
}
