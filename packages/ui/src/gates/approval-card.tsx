import type { JSX, ReactNode } from "react";
import { HumanAction } from "../attribution/human-action";
import type { Actor } from "../attribution/actor";
import { Button } from "../components/button";
import { cn } from "../cn";

// ApprovalCard (E7; P-04-T40; SHL-10): an agent's output a person approves. The reasoning comes
// in through `reasoning` as a node (the caller renders agent prose through AgentText); the diff
// rows show each change with its prior value struck; evidence rows open the source; a policy note
// and the set link close it. Approve is a HumanAction, so it never renders for the agent, and it
// stays disabled while any changed row lacks a citation.

export interface DiffRow {
  key: string;
  label: string;
  before: string | null;
  after: string | null;
  /** Citations the change carries; 0 blocks Approve. */
  cites: number;
  /** Why the value changes ("K-1 box 2"); SHL-10's Cause column. */
  cause?: string | null;
}

export interface EvidenceRow {
  key: string;
  label: string;
  meta?: string;
  onOpen?: () => void;
}

export interface ApprovalCardProps {
  title: string;
  actor: Actor;
  reasoning?: ReactNode;
  rows: readonly DiffRow[];
  evidence?: readonly EvidenceRow[];
  policyNote?: string;
  setLink?: { label: string; onOpen?: () => void };
  /** Shown beside the disabled Approve when a change has no citation. */
  uncitedLabel?: (n: number) => string;
  busy?: boolean;
  onApprove?: () => void;
  onReject?: () => void;
  rejectLabel?: string;
  /** What Approve acts on: "adjustments" makes "Approve adjustments". */
  approveObject?: string;
  /** More actions beside Reject ("Edit…", "Ask follow-up…"). */
  actions?: ReactNode;
  /** Under the change rows: a totals row ("Net change to Form 1040 total income · 0 · tie"). */
  afterRows?: ReactNode;
  /** The After cell, replaced in edit mode (SHL-10 "Edit…"). */
  renderAfter?: (row: DiffRow) => ReactNode;
  /** A meta line under the footer ("Approving creates Checkpoint 6 and logs to Activity."). */
  footnote?: string;
  /** SHL-10's sheet footer: Approve full width, the other actions in a row beneath. */
  stacked?: boolean;
  /** Extra reasons Approve stays disabled (an edit without its citation note). */
  approveBlocked?: boolean;
  className?: string;
}

export function uncited(rows: readonly DiffRow[]): number {
  return rows.filter((r) => r.after !== r.before && r.cites === 0).length;
}

export function ApprovalCard({
  title,
  actor,
  reasoning,
  rows,
  evidence = [],
  policyNote,
  setLink,
  uncitedLabel = (n) => `${String(n)} ${n === 1 ? "change has" : "changes have"} no citation`,
  busy = false,
  onApprove,
  onReject,
  rejectLabel = "Reject…",
  approveObject,
  actions,
  renderAfter,
  afterRows,
  footnote,
  stacked = false,
  approveBlocked = false,
  className,
}: ApprovalCardProps): JSX.Element {
  const missing = uncited(rows);
  const approve = (
    <HumanAction
      verb="Approve"
      {...(approveObject === undefined ? {} : { object: approveObject })}
      actor={actor}
      disabled={busy || missing > 0 || approveBlocked}
      {...(missing > 0 ? { "aria-describedby": "approval-uncited" } : {})}
      {...(stacked ? { className: "w-full" } : {})}
      onClick={onApprove}
    />
  );
  const reject =
    onReject === undefined ? null : (
      <Button variant="secondary" opensDialog onClick={onReject} disabled={busy}>
        {rejectLabel}
      </Button>
    );
  const missingNote =
    missing > 0 ? (
      <span id="approval-uncited" className="text-meta text-red-ink">
        {uncitedLabel(missing)}
      </span>
    ) : null;
  return (
    <section
      aria-label={title}
      data-gate="approval"
      className={cn("flex flex-col overflow-hidden rounded-nested bg-card shadow-e1", className)}
    >
      <header className="flex min-h-[33px] items-center border-b-[0.5px] border-hair bg-band-hd px-[12px]">
        <h3 className="text-section">{title}</h3>
      </header>
      {reasoning !== undefined && (
        <div data-gate="reasoning" className="px-[12px] py-[10px] text-para text-ink-2">
          {reasoning}
        </div>
      )}
      <ul
        aria-label="Changes"
        className="divide-y-[0.5px] divide-hair border-t-[0.5px] border-hair"
      >
        {rows.map((r) => (
          <li
            key={r.key}
            data-row={r.key}
            className="grid grid-cols-[minmax(0,1fr)_auto] gap-[12px] px-[12px] py-[8px] text-body"
          >
            <span className="flex flex-col">
              {r.label}
              {r.cause !== undefined && r.cause !== null && (
                <span className="text-meta text-ink-3">{r.cause}</span>
              )}
            </span>
            <span className="flex items-center gap-[8px] tabular-nums">
              {r.before !== null && r.before !== r.after && (
                <s className="text-ink-3">
                  <span className="sr-only">changed from </span>
                  {r.before}
                </s>
              )}
              {renderAfter === undefined ? (
                <span className="font-medium">{r.after ?? "—"}</span>
              ) : (
                renderAfter(r)
              )}
              {r.after !== r.before && r.cites === 0 && (
                <span className="text-meta text-red-ink">no citation</span>
              )}
            </span>
          </li>
        ))}
      </ul>
      {afterRows}
      {evidence.length > 0 && (
        <ul
          aria-label="Evidence"
          className="divide-y-[0.5px] divide-hair border-t-[0.5px] border-hair"
        >
          {evidence.map((e) => (
            <li
              key={e.key}
              className="flex items-center justify-between px-[12px] py-[8px] text-dense"
            >
              <button type="button" className="text-left font-medium" onClick={e.onOpen}>
                {e.label}
              </button>
              {e.meta !== undefined && <span className="text-meta text-ink-3">{e.meta}</span>}
            </li>
          ))}
        </ul>
      )}
      {policyNote !== undefined && (
        <p className="border-t-[0.5px] border-hair px-[12px] py-[8px] text-meta text-ink-3">
          {policyNote}
        </p>
      )}
      {stacked ? (
        <footer className="flex flex-col gap-[8px] border-t-[0.5px] border-hair px-[12px] py-[10px]">
          {missingNote}
          {approve}
          <span className="flex items-center gap-[8px] [&>*]:flex-1">
            {actions}
            {reject}
          </span>
          {footnote !== undefined && <p className="text-meta text-ink-3">{footnote}</p>}
        </footer>
      ) : (
        <footer className="flex items-center justify-between gap-[8px] border-t-[0.5px] border-hair px-[12px] py-[10px]">
          {setLink !== undefined ? (
            <button type="button" className="text-dense text-ink-2" onClick={setLink.onOpen}>
              {setLink.label} <span aria-hidden="true">›</span>
            </button>
          ) : (
            <span />
          )}
          <span className="flex items-center gap-[8px]">
            {missingNote}
            {actions}
            {reject}
            {approve}
          </span>
        </footer>
      )}
    </section>
  );
}
