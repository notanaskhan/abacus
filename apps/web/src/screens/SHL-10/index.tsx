import type { AgentProposalOut, ProposalRowOut } from "@abacus/api-client";
import {
  AgentText,
  type Actor,
  ApprovalCard,
  Button,
  Dialog,
  type DiffRow,
  HumanAction,
  RegistryStatus,
  SheetModal,
  StatusPill,
  ValueRow,
  amount,
  formatActor,
  time,
  toast,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { useOpenSourceViewer } from "../../app-core/overlay-host";
import { useSession } from "../../app-core/session";
import {
  REJECT_REASONS,
  type RejectReason,
  conflictOf,
  useGate,
  useProposal,
  useProposalWrites,
} from "../../domain/review";
import { COPY } from "./copy";

// SHL-10 · Approve agent output (P-04-T41; SPEC-360; the handoff's SHL-10 folder): the O3 sheet at
// `?ov=approve:<proposalRef>` where a person approves, edits or rejects one proposal. Frames built
// here (fixtures/seed/review.ts, P-04-T34):
//
//   a  the Feld K-1 treatment: reasoning, four changes with the prior value struck, the totals
//      tie, three evidence rows opening SHL-08, the policy note, "Approve adjustments"
//   b  a in edit mode: each After cell is editable and an edited row needs its citation note;
//      the CTA reads "Approve with edits" and sends only the edited rows
//   c  an uncited fifth change: "Unsupported" in its Cause, Approve disabled with "1 change has no
//      citation", "Ask follow-up…" promoted
//   f  reject with a reason from the picker; the result line names the person and the reason
//
// d, e, e′ and g (thresholds, batch and the set link) are later rows of P-04. Approving is a
// HumanAction on the signed-in person, so the agent never sees it (INV-1); the write waits for the
// server (never optimistic), and Undo calls only the compensating command.

/** A server value as the diff shows it: numbers grouped ("307,900", "14,900.00"), text as sent. */
export function shown(v: string | null): string {
  if (v === null) return "—";
  if (!/^-?\d+(\.\d+)?$/u.test(v)) return v;
  return amount(v, v.includes(".") ? "cents" : "whole", { zero: "explicit" }).text;
}

function diffRows(rows: readonly ProposalRowOut[]): DiffRow[] {
  return rows.map((r) => ({
    key: String(r.n),
    label: r.label,
    before: r.before === null ? null : shown(r.before),
    after: r.after === null ? null : shown(r.after),
    cites: r.citation_ids.length,
    cause: r.unsupported ? COPY.unsupported : r.cause,
  }));
}

interface Edit {
  after: string;
  note: string;
}

export type ApproveMode = "view" | "edit" | "reject";

export interface ApproveSheetProps {
  proposalRef: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The frame it opens in: b opens in edit mode, f with the reject dialog. */
  initialMode?: ApproveMode;
}

export function ApproveSheet({
  proposalRef,
  open,
  onOpenChange,
  initialMode = "view",
}: ApproveSheetProps): JSX.Element {
  const session = useSession();
  const query = useProposal(proposalRef);
  const proposal = query.data;
  const actor: Actor =
    session.user === null ? { kind: "system" } : { kind: "human", name: session.user.displayName };
  return (
    <SheetModal
      open={open}
      onOpenChange={onOpenChange}
      title={COPY.title}
      meta={
        proposal === undefined ? undefined : (
          <span className="text-meta text-ink-3">{proposal.context_label}</span>
        )
      }
    >
      {proposal === undefined ? (
        <p className="p-[12px] text-meta text-ink-3">
          {query.isError ? COPY.missing : COPY.loading}
        </p>
      ) : (
        <Proposal
          key={`${proposal.ref}:${String(proposal.version)}`}
          proposal={proposal}
          actor={actor}
          initialMode={initialMode}
        />
      )}
    </SheetModal>
  );
}

function Proposal({
  proposal,
  actor,
  initialMode,
}: {
  proposal: AgentProposalOut;
  actor: Actor;
  initialMode: ApproveMode;
}): JSX.Element {
  const writes = useProposalWrites(proposal);
  const openViewer = useOpenSourceViewer();
  const allowed = new Set(proposal.allowed_actions);
  const [editing, setEditing] = useState(
    initialMode === "edit" && allowed.has("proposal.approve"),
  );
  const [edits, setEdits] = useState<Record<number, Edit>>({});
  const [rejecting, setRejecting] = useState(
    initialMode === "reject" && allowed.has("proposal.reject"),
  );
  const [asking, setAsking] = useState(false);

  const changed = Object.entries(edits)
    .map(([n, e]) => ({ n: Number(n), ...e }))
    .filter((e) => {
      const row = proposal.rows.find((r) => r.n === e.n);
      return row !== undefined && e.after !== (row.after ?? "");
    });
  const notesMissing = changed.some((e) => e.note.trim() === "");

  const gate = useGate({
    command: () =>
      writes.approve(
        changed.map((e) => ({ n: e.n, after: e.after, citation_note: e.note.trim() })),
      ),
    compensate: (result) =>
      result.decision === null ? Promise.resolve() : writes.undo(result.decision.id),
    doneText: () => COPY.toasts.approved,
    failedText: COPY.toasts.failed,
  });

  const rows = diffRows(proposal.rows);
  const decided = proposal.decision;
  const pending = proposal.state === "pending";
  const agent = formatActor(
    proposal.agent_run_id === null ? { kind: "system" } : { kind: "agent" },
  );

  return (
    <div className="flex flex-col gap-[12px] p-[12px]">
      <div className="flex items-center gap-[8px] text-body">
        <span className="font-medium">
          {agent} {COPY.proposed(proposal.change_count)}
        </span>
        <span className="flex-1" />
        <RegistryStatus object="proposal" code={proposal.state} />
        <span className="text-meta text-ink-3">{time(proposal.proposed_at)}</span>
      </div>
      {decided !== null && (
        <p
          data-decision={decided.decision}
          className={
            decided.decision === "rejected" ? "text-body text-red-ink" : "text-body text-green-ink"
          }
        >
          {decided.decision === "rejected"
            ? COPY.rejected(
                decided.decided_by_name,
                decided.reason_code === null ? "" : COPY.reasons[decided.reason_code],
              )
            : COPY.approved(decided.decided_by_name)}
        </p>
      )}
      <ApprovalCard
        title={COPY.reasoning}
        actor={pending && allowed.has("proposal.approve") ? actor : { kind: "system" }}
        reasoning={<AgentText text={proposal.reasoning} />}
        rows={rows}
        afterRows={proposal.totals.map((t) => (
          <p
            key={t.label}
            className="flex items-center gap-[8px] border-t-[0.5px] border-stroke px-[12px] py-[8px] text-body font-medium"
          >
            <span className="flex-1">{t.label}</span>
            <span className="tabular-nums">{shown(t.value)}</span>
            {t.ties && (
              <StatusPill variant="green" size="micro">
                {COPY.tie}
              </StatusPill>
            )}
          </p>
        ))}
        evidence={proposal.evidence.map((e) => ({
          key: e.evidence_version_id,
          label: e.label,
          meta: COPY.citations(e.citation_count),
          onOpen: () => {
            openViewer({ evidenceVersionId: e.evidence_version_id });
          },
        }))}
        {...(proposal.policy?.note == null ? {} : { policyNote: proposal.policy.note })}
        {...(editing
          ? {
              renderAfter: (row: DiffRow) => {
                const source = proposal.rows.find((r) => String(r.n) === row.key);
                if (source === undefined) return null;
                const value = edits[source.n]?.after ?? source.after ?? "";
                return (
                  <input
                    aria-label={`${row.label}: after`}
                    value={value}
                    onChange={(event) => {
                      const after = event.target.value;
                      setEdits((prev) => ({
                        ...prev,
                        [source.n]: { after, note: prev[source.n]?.note ?? "" },
                      }));
                    }}
                    className="w-[96px] rounded-sheet bg-nested px-[6px] text-right font-medium tabular-nums"
                  />
                );
              },
              approveObject: COPY.approveEdits,
            }
          : { approveObject: COPY.approveObject })}
        uncitedLabel={COPY.uncited}
        approveBlocked={!pending || (editing && (changed.length === 0 || notesMissing))}
        busy={gate.phase === "busy"}
        stacked
        onApprove={() => void gate.run()}
        {...(pending && allowed.has("proposal.reject")
          ? {
              onReject: () => {
                setRejecting(true);
              },
            }
          : {})}
        rejectLabel={COPY.reject}
        actions={
          pending ? (
            <>
              {allowed.has("proposal.approve") && (
                <Button
                  variant="tonal"
                  onClick={() => {
                    setEditing((e) => !e);
                    setEdits({});
                  }}
                >
                  {editing ? COPY.cancelEdit : COPY.edit}
                </Button>
              )}
              {allowed.has("proposal.follow_up") && (
                <Button
                  variant={rows.some((r) => r.cites === 0) ? "primary" : "secondary"}
                  opensDialog
                  onClick={() => {
                    setAsking(true);
                  }}
                >
                  {COPY.followUp}
                </Button>
              )}
            </>
          ) : null
        }
        footnote={COPY.footnote}
      />
      {editing && changed.length > 0 && (
        <section aria-label={COPY.citationNote} className="rounded-nested bg-card shadow-e1">
          {changed.map((e) => {
            const row = proposal.rows.find((r) => r.n === e.n);
            return (
              <ValueRow
                key={e.n}
                kind="text"
                label={`${COPY.citationNote} · ${row?.label ?? ""}`}
                value={e.note}
                placeholder={COPY.citationRequired}
                onChange={(note) => {
                  setEdits((prev) => ({ ...prev, [e.n]: { after: e.after, note } }));
                }}
              />
            );
          })}
        </section>
      )}
      {gate.phase === "blocked" && gate.blocked !== null && (
        <p role="alert" className="text-meta text-red-ink">
          {gate.blocked.code === "proposal_changed" ? COPY.toasts.changed : COPY.toasts.failed}
        </p>
      )}
      <RejectDialog
        open={rejecting}
        onClose={() => {
          setRejecting(false);
        }}
        onReject={async (reason, note) => {
          try {
            await writes.reject(reason, note);
            setRejecting(false);
            toast.show({ kind: "success", text: COPY.toasts.rejected });
          } catch (error) {
            const conflict = conflictOf(error);
            toast.show({
              kind: "error",
              text:
                conflict?.code === "proposal_changed" ? COPY.toasts.changed : COPY.toasts.failed,
            });
          }
        }}
      />
      <FollowUpDialog
        open={asking}
        actor={actor}
        onClose={() => {
          setAsking(false);
        }}
        onSend={async (text) => {
          try {
            await writes.followUp(text);
            setAsking(false);
            toast.show({ kind: "success", text: COPY.followUpDialog.sent });
          } catch {
            toast.show({ kind: "error", text: COPY.toasts.failed });
          }
        }}
      />
    </div>
  );
}

function RejectDialog({
  open,
  onClose,
  onReject,
}: {
  open: boolean;
  onClose: () => void;
  onReject: (reason: RejectReason, note: string | null) => Promise<void>;
}): JSX.Element {
  const [reason, setReason] = useState<RejectReason | undefined>(undefined);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={COPY.rejectDialog.title}
      size="md"
      dirty={reason !== undefined || note !== ""}
    >
      <div className="flex flex-col">
        <ValueRow
          kind="select"
          label={COPY.rejectDialog.reason}
          {...(reason === undefined ? {} : { value: reason })}
          options={REJECT_REASONS.map((r) => ({ value: r, label: COPY.reasons[r] }))}
          onChange={(v) => {
            setReason(v as RejectReason);
          }}
        />
        <ValueRow
          kind="paragraph"
          label={COPY.rejectDialog.note}
          value={note}
          onChange={setNote}
        />
        <div className="flex justify-end gap-[8px] pt-[12px]">
          <Button variant="secondary" onClick={onClose}>
            {COPY.rejectDialog.cancel}
          </Button>
          <Button
            variant="destructive"
            disabled={reason === undefined || busy}
            onClick={() => {
              if (reason === undefined) return;
              setBusy(true);
              void onReject(reason, note.trim() === "" ? null : note.trim()).finally(() => {
                setBusy(false);
              });
            }}
          >
            {COPY.rejectDialog.reject}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

function FollowUpDialog({
  open,
  actor,
  onClose,
  onSend,
}: {
  open: boolean;
  actor: Actor;
  onClose: () => void;
  onSend: (text: string) => Promise<void>;
}): JSX.Element {
  const [text, setText] = useState("");
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={COPY.followUpDialog.title}
      size="md"
      dirty={text !== ""}
    >
      <ValueRow
        kind="paragraph"
        label={COPY.followUpDialog.label}
        value={text}
        onChange={setText}
      />
      <div className="flex justify-end pt-[12px]">
        <HumanAction
          verb="Send"
          actor={actor}
          disabled={text.trim() === ""}
          onClick={() => {
            void onSend(text.trim());
          }}
        />
      </div>
    </Dialog>
  );
}
