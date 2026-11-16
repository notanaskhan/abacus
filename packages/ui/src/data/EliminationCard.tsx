import type { JSX, ReactNode } from "react";
import { AgentText } from "../agent-text";
import { cn } from "../cn";
import { Amount } from "../components/amount";
import { Button } from "../components/button";
import { Pill } from "../components/pill";

// C-38 EliminationCard (A-09-T15; AUD-33 a, b, c): one elimination in the docked drawer. The
// header names its code, level, description, the server's amount and its status; expanded, its
// lines, the code's computation, its citations and the provenance. A proposed entry carries the
// agent's note (AgentText) and the person's Approve, Edit and Reject; Approve stays disabled while
// the server says the entry is off (`offBy`). The agent never approves or posts (ADR-005).

export type EliminationStatus = "proposed" | "approved" | "posted" | "rejected";

export interface EliminationLine {
  caption: string;
  debit: string;
  credit: string;
}

export interface EliminationCardProps {
  code: string;
  level: number;
  description: string;
  amount: string;
  status: EliminationStatus;
  lines: readonly EliminationLine[];
  computation?: string | null | undefined;
  citations?: readonly string[];
  provenance?: string | undefined;
  agentNote?: string | undefined;
  /** The server's off amount when debits and credits differ ("10000.00"). */
  offBy?: string | null | undefined;
  subline?: string | undefined;
  expanded?: boolean;
  selected?: boolean;
  onToggle?: () => void;
  onApprove?: () => void;
  onEdit?: () => void;
  onReject?: () => void;
  /** Words for the controls (the screen's copy). */
  words: {
    level: (n: number) => string;
    status: Record<EliminationStatus, string>;
    approve: string;
    edit: string;
    reject: string;
    dr: string;
    cr: string;
    off: (amount: string) => string;
  };
}

function Line({
  side,
  caption,
  amount,
}: {
  side: string;
  caption: string;
  amount: string;
}): JSX.Element {
  return (
    <li className="flex h-[24px] items-center gap-[8px] text-[12px]">
      <span className="w-[20px] text-ink-3">{side}</span>
      <span className="flex-1">{caption}</span>
      <Amount value={amount} style="whole" />
    </li>
  );
}

export function EliminationCard(p: EliminationCardProps): JSX.Element {
  const W = p.words;
  const off = p.offBy !== null && p.offBy !== undefined && Number(p.offBy) !== 0;
  const pill: Record<EliminationStatus, ReactNode> = {
    posted: <Pill variant="green">{W.status.posted}</Pill>,
    approved: <Pill variant="green-tint">{W.status.approved}</Pill>,
    proposed: <Pill variant="outline">{W.status.proposed}</Pill>,
    rejected: <Pill variant="muted">{W.status.rejected}</Pill>,
  };
  return (
    <article
      data-elimination={p.code}
      data-status={p.status}
      aria-selected={p.selected === true}
      className={cn(
        "rounded-[10px] bg-card px-[12px] py-[10px] shadow-e1",
        p.selected === true && "inset-ring-[1.5px] inset-ring-espresso",
      )}
    >
      <button
        type="button"
        aria-expanded={p.expanded === true}
        onClick={p.onToggle}
        className="flex w-full items-center gap-[8px] text-left"
      >
        <span className="font-mono text-[11.5px]">{p.code}</span>
        <span className="rounded-[4px] bg-nested px-[5px] text-[10.5px] font-medium text-ink-2">
          {W.level(p.level)}
        </span>
        <span className="flex-1 truncate text-[12.5px] font-medium">{p.description}</span>
        <span className="text-[13px] font-medium tabular-nums">
          <Amount value={p.amount} style="whole" />
        </span>
        {pill[p.status]}
      </button>
      {p.subline !== undefined && <p className="mt-[4px] text-[11.5px] text-ink-3">{p.subline}</p>}
      {off && (
        <p
          data-off={p.offBy ?? ""}
          className="mt-[6px] rounded-[6px] bg-red-tint px-[8px] py-[4px] text-[12px] text-red-ink"
        >
          {W.off(p.offBy ?? "0")}
        </p>
      )}
      {p.expanded === true && (
        <div className="mt-[8px] flex flex-col gap-[8px]">
          <ul>
            {p.lines.map((l) =>
              Number(l.debit) > 0 ? (
                <Line key={`dr-${l.caption}`} side={W.dr} caption={l.caption} amount={l.debit} />
              ) : (
                <Line key={`cr-${l.caption}`} side={W.cr} caption={l.caption} amount={l.credit} />
              ),
            )}
          </ul>
          {p.computation !== null && p.computation !== undefined && (
            <p
              data-computation
              className="rounded-[8px] bg-shell px-[10px] py-[8px] text-[12px] leading-[1.5]"
            >
              {p.computation}
            </p>
          )}
          {p.agentNote !== undefined && (
            <div className="text-[12px] text-ink-2">
              <AgentText text={p.agentNote} />
            </div>
          )}
          {(p.citations ?? []).length > 0 && (
            <div className="flex flex-wrap gap-[6px]">
              {(p.citations ?? []).map((c) => (
                <span
                  key={c}
                  className="inline-flex h-[22px] items-center rounded-pill bg-nested px-[8px] text-[11.5px] text-ink-2"
                >
                  {c}
                </span>
              ))}
            </div>
          )}
          {p.provenance !== undefined && <p className="text-[11px] text-ink-3">{p.provenance}</p>}
        </div>
      )}
      {p.status === "proposed" && (
        <div className="mt-[8px] flex gap-[6px]">
          <Button
            variant="primary"
            size="sm"
            disabled={off || p.onApprove === undefined}
            onClick={p.onApprove}
          >
            {W.approve}
          </Button>
          <Button variant="ghost" size="sm" onClick={p.onEdit}>
            {W.edit}
          </Button>
          <Button variant="ghost" size="sm" onClick={p.onReject}>
            {W.reject}
          </Button>
        </div>
      )}
    </article>
  );
}
