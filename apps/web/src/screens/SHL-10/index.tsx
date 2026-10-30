import type { AgentProposalOut, ProposalRowOut } from "@abacus/api-client";
import {
  AgentText,
  type Actor,
  ApprovalCard,
  Button,
  Dialog,
  type DiffRow,
  Icon,
  StatusDisc,
  Tooltip,
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
import { type JSX, type ReactNode, useState } from "react";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
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
// P-04-T42 adds d (AJE-05 over BH AJE thresholds v2: no Approve, "Send to Priya Raman for
// approval", the policy row's words), e (the within-threshold batch as a JE table, "Approve 4 under
// BH AJE thresholds v2"), e′ (the card collapses to the line naming the person and the policy, with
// Undo while it lasts) and g (part of a set: the link row to SHL-19, which opens the package and
// approves nothing). Approving is a HumanAction on the signed-in person, so the agent never sees it
// (INV-1); the write waits for the server (never optimistic), and Undo calls only the compensating
// command.

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
      title={
        proposal?.kind === "adjusting_entry_batch"
          ? COPY.batchTitle(proposal.change_count)
          : COPY.title
      }
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

  const now = useNow();
  const rows = diffRows(proposal.rows);
  const decided = proposal.decision;
  const pending = proposal.state === "pending";
  const policy = proposal.policy;
  const batch = proposal.kind === "adjusting_entry_batch";
  const routed = policy?.result === "review_required" && allowed.has("proposal.route");
  const [routing, setRouting] = useState(false);
  const [undoing, setUndoing] = useState(false);
  const agent = formatActor(
    proposal.agent_run_id === null ? { kind: "system" } : { kind: "agent" },
  );

  return (
    <div className="flex flex-col gap-[12px] p-[12px]">
      <div className="flex items-center gap-[8px] text-body">
        <span className="font-medium">
          {agent}{" "}
          {batch && policy?.policy_name != null
            ? COPY.proposedEntries(proposal.change_count, policy.policy_name)
            : COPY.proposed(proposal.change_count)}
        </span>
        <span className="flex-1" />
        <RegistryStatus object="proposal" code={proposal.state} />
        <span className="text-meta text-ink-3">{time(proposal.proposed_at)}</span>
      </div>
      {decided !== null && batch && decided.decision === "approved" ? (
        // e′: the card collapses to the line; Undo lasts until the server's `undo_until`.
        <p
          data-decision="approved"
          className="flex items-center gap-[8px] text-body font-medium text-green-ink"
        >
          <span className="flex-1">
            {COPY.approvedUnder(
              decided.decided_by_name,
              policy?.policy_name ?? "",
              time(decided.decided_at),
            )}
          </span>
          {allowed.has("proposal.undo") &&
            decided.undo_until !== null &&
            Date.parse(decided.undo_until) > now.getTime() && (
              <Button
                variant="ghost"
                size="sm"
                disabled={undoing}
                onClick={() => {
                  setUndoing(true);
                  writes
                    .undo(decided.id)
                    .then(() => {
                      toast.show({ kind: "success", text: COPY.undone });
                    })
                    .catch(() => {
                      toast.show({ kind: "error", text: COPY.toasts.failed });
                    })
                    .finally(() => {
                      setUndoing(false);
                    });
                }}
              >
                {COPY.undo}
              </Button>
            )}
        </p>
      ) : decided !== null ? (
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
      ) : null}
      {!(batch && decided?.decision === "approved") && (
        <ApprovalCard
          title={COPY.reasoning}
          actor={pending && allowed.has("proposal.approve") ? actor : { kind: "system" }}
          {...(proposal.reasoning === ""
            ? {}
            : { reasoning: <AgentText text={proposal.reasoning} /> })}
          rows={rows}
          {...(batch ? { rowsContent: <BatchTable rows={proposal.rows} /> } : {})}
          {...(proposal.set === null
            ? {}
            : {
                setRow: (
                  <SetRow
                    label={COPY.setRow(
                      proposal.set.label,
                      proposal.set.results,
                      proposal.set.exceptions,
                    )}
                  />
                ),
              })}
          {...(routed && policy.routed_to_user_id != null
            ? {
                primary: (
                  <span className="flex w-full flex-col gap-[4px]">
                    <HumanAction
                      verb="Send"
                      object={`to ${policy.routed_to_name ?? ""} for approval`}
                      actor={actor}
                      disabled={!pending || routing}
                      className="w-full"
                      onClick={() => {
                        const to = policy.routed_to_user_id;
                        if (to === null) return;
                        setRouting(true);
                        writes
                          .route(to)
                          .then(() => {
                            toast.show({
                              kind: "success",
                              text: COPY.sentTo(policy.routed_to_name ?? ""),
                            });
                          })
                          .catch(() => {
                            toast.show({ kind: "error", text: COPY.toasts.failed });
                          })
                          .finally(() => {
                            setRouting(false);
                          });
                      }}
                    />
                    <span className="text-meta text-ink-3">{COPY.yourLimit}</span>
                  </span>
                ),
              }
            : {})}
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
          {...(proposal.policy?.note == null || routed
            ? {}
            : { policyNote: proposal.policy.note })}
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
            : {
                approveObject: batch
                  ? COPY.approveBatch(proposal.change_count, policy?.policy_name ?? "")
                  : proposal.kind === "procedure_conclusion"
                    ? COPY.approveConclusion
                    : COPY.approveObject,
              })}
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
      )}
      {routed && policy.note != null && (
        <p
          data-policy="review_required"
          className="flex items-center gap-[8px] text-meta text-amber-ink"
        >
          <StatusDisc state="todo" size={13} />
          {policy.note}
        </p>
      )}
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

/** e: the batch as a JE table (Entry · Debit · Credit · Policy), the server's lines verbatim. */
function BatchTable({ rows }: { rows: readonly ProposalRowOut[] }): JSX.Element {
  const th = "px-[12px] py-[6px] text-left text-th font-normal text-ink-2";
  return (
    <table
      aria-label="Entries"
      className="w-full border-t-[0.5px] border-hair text-dense tabular-nums"
    >
      <thead className="bg-band-hd">
        <tr>
          <th className={th}>{COPY.je.entry}</th>
          <th className={th}>{COPY.je.debit}</th>
          <th className={th}>{COPY.je.credit}</th>
          <th className={th}>{COPY.je.policy}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.n} data-row={r.n} className="border-t-[0.5px] border-hair align-top">
            <td className="px-[12px] py-[6px]">{r.label}</td>
            <td className="px-[12px] py-[6px]">{r.before ?? "—"}</td>
            <td className="px-[12px] py-[6px]">{r.after ?? "—"}</td>
            <td className="px-[12px] py-[6px]">
              <span className="inline-flex items-center gap-[6px]">
                <StatusDisc state="done" size={13} />
                {r.cause}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** g (R2): the link row to SHL-19. It opens the package; it never approves anything. SHL-19 is a
 * planned screen, so the link is drawn (tooltip-only) where planned screens are, else absent. */
function SetRow({ label }: { label: string }): JSX.Element {
  const link: ReactNode = PLANNED_VISIBLE ? (
    <Tooltip content={COPY.reviewAllHint}>
      <span className="text-dense font-medium text-ink">
        {COPY.reviewAll} <span className="text-ink-3">→</span>
      </span>
    </Tooltip>
  ) : null;
  return (
    <div
      data-set-row=""
      className="flex h-[36px] items-center gap-[8px] border-t-[0.5px] border-hair px-[12px]"
    >
      <Icon name="layers" size={14} className="text-ink-3" />
      <span className="flex-1 truncate text-dense text-ink-2">{label}</span>
      {link}
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
