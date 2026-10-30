import type { CheckpointDetailOut, CheckpointItemOut } from "@abacus/api-client";
import { checkpointCreateMutation } from "@abacus/api-client/query";
import {
  type Actor,
  AgentText,
  Button,
  Dialog,
  Drawer,
  EmptyState,
  HumanAction,
  Icon,
  type IconName,
  Menu,
  Pill,
  Segmented,
  StatusPill,
  ValueRow,
  amount,
  date as formatDate,
  formatActor,
  time,
  toast,
} from "@abacus/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import {
  type CheckpointFilter,
  type CheckpointTarget,
  useCheckpoint,
  useCheckpointHistory,
  useCheckpointWrites,
} from "../../domain/review";
import { COPY } from "./copy";

// SHL-16 · Checkpoint diff drawer (P-04-T43; SPEC-360; the handoff's SHL-16 folder): the O2 drawer
// at `?ov=checkpoints:<target_type>:<target_id>` over a record (the Feld 2025 Form 1040). Frames:
//
//   a  Checkpoint 6 proposed by the agent, expanded: steps, field diff, the tie; Approve / Reject…
//   b  approved: "Current" moves to 6 with "Approved · Samuel Ito · 9:26 AM"
//   c  an older checkpoint (3) selected: its steps and diff against Current; Restore… only, with the
//      dialog "This creates Checkpoint 7 as a copy…" (Restore always makes a new checkpoint)
//   d  rename and star: Checkpoint 5 named "Before K-1 treatment", star filled
//   e  rejected: "Rejected" with "Samuel Ito · reason: Wait for final K-1"
//   f  empty: "No checkpoints yet." with "Save checkpoint…"
//
// The filter offers Agent only · Named only · All (the server filters). Approve is a HumanAction on
// the signed-in person (INV-1); every write waits for the server and carries the hash the person
// saw; nothing is optimistic. The Assistant segment opens TAX-08 (planned, tooltip-only).

const STEP_ICON: Readonly<Record<string, IconName>> = {
  analyzed: "scan-search",
  updated_worksheet: "list-plus",
  created_worksheet: "list-plus",
  skipped_worksheet: "ban",
  self_check: "circle-check",
  imported: "download",
};

function shown(v: string | null): string {
  if (v === null) return "—";
  if (!/^-?\d+(\.\d+)?$/u.test(v)) return v;
  return amount(v, v.includes(".") ? "cents" : "whole", { zero: "explicit" }).text;
}

function Detail({ detail }: { detail: CheckpointDetailOut }): JSX.Element {
  // An agent-authored checkpoint's steps are the agent's words: plain text through AgentText.
  const agent = detail.checkpoint.author_kind === "agent";
  return (
    <div
      data-checkpoint-detail={detail.checkpoint.seq}
      className="mt-[8px] flex flex-col gap-[8px] rounded-nested bg-card"
    >
      <ol aria-label="Steps" className="flex flex-col">
        {detail.steps.map((s, i) => (
          <li
            key={`${s.kind}-${String(i)}`}
            className="flex min-h-[40px] gap-[8px] px-[10px] py-[6px]"
          >
            <Icon
              name={STEP_ICON[s.kind] ?? "circle"}
              size={14}
              className="mt-[2px] flex-none text-ink-2"
            />
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="flex items-baseline gap-[8px]">
                <span className="flex-1 text-body font-medium">
                  {agent ? (
                    <AgentText text={s.title} inline className="text-body text-ink" />
                  ) : (
                    s.title
                  )}
                </span>
                <span className="text-meta text-ink-3">{time(s.at)}</span>
              </span>
              {s.detail !== null &&
                (agent ? (
                  <AgentText text={s.detail} inline className="text-dense text-ink-2" />
                ) : (
                  <span className="text-dense text-ink-2">{s.detail}</span>
                ))}
            </span>
          </li>
        ))}
      </ol>
      {detail.diff.length > 0 && (
        <table
          aria-label="Field diff"
          className="mx-[10px] mb-[10px] text-dense shadow-[inset_0_0_0_0.5px_var(--color-hair)]"
        >
          <thead className="bg-band-hd">
            <tr className="h-[30px] text-left text-th font-medium text-ink-2">
              <th className="px-[8px]">{COPY.columns.field}</th>
              <th className="px-[8px]">{COPY.columns.change}</th>
              <th className="px-[8px]">{COPY.columns.cause}</th>
            </tr>
          </thead>
          <tbody>
            {detail.diff.map((r) => (
              <tr
                key={r.field_key}
                data-field={r.field_key}
                className="h-[34px] border-t-[0.5px] border-hair"
              >
                <td className="px-[8px]">{r.label}</td>
                <td className="px-[8px] tabular-nums">
                  <s className="text-ink-3">{shown(r.old)}</s>
                  <span className="text-ink-3"> → </span>
                  <span className="font-medium">{shown(r.new)}</span>
                </td>
                <td className="px-[8px] text-ink-2">{r.cause}</td>
              </tr>
            ))}
            {detail.totals.map((t) => (
              <tr key={t.label} className="h-[34px] border-t-[0.5px] border-stroke font-medium">
                <td className="px-[8px]">{t.label}</td>
                <td className="px-[8px] tabular-nums">{shown(t.value)}</td>
                <td className="px-[8px]">
                  {t.ties && (
                    <StatusPill variant="green" size="micro">
                      {COPY.tie}
                    </StatusPill>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function StatePill({ cp }: { cp: CheckpointItemOut }): JSX.Element | null {
  if (cp.status === "proposed")
    return (
      <Pill variant="amber" size="sm">
        Proposed
      </Pill>
    );
  if (cp.status === "approved" && cp.current && cp.decision !== null) return null;
  if (cp.status === "approved")
    return (
      <Pill variant="green-tint" size="sm">
        Approved
      </Pill>
    );
  if (cp.status === "rejected")
    return (
      <Pill variant="red-tint" size="sm">
        Rejected
      </Pill>
    );
  return null;
}

function Card({
  cp,
  open,
  now,
  onToggle,
  renaming,
  onRename,
  onStar,
  onStartRename,
}: {
  cp: CheckpointItemOut;
  open: boolean;
  now: Date;
  onToggle: () => void;
  renaming: boolean;
  onRename: (name: string) => void;
  onStar: () => void;
  onStartRename: () => void;
}): JSX.Element {
  const [name, setName] = useState(cp.name ?? "");
  const canRename = cp.allowed_actions.includes("checkpoint.rename");
  // An import's author line names the engine version it came from (P-04-T47: "Imported from CCH
  // Axcess 2025I:FeldJ:V3"); an agent's is the Agent; a person's is their name.
  const author =
    cp.author_kind === "agent"
      ? formatActor({ kind: "agent" })
      : cp.author_kind === "import"
        ? (cp.summary ?? cp.author_name)
        : cp.author_name;
  const decided = cp.decision;
  const when = formatDate(cp.created_at, { now });
  const meta = [
    `${when}, ${time(cp.created_at)}`,
    author,
    decided !== null && decided.decision === "approved" && !cp.current
      ? COPY.approvedBy(decided.decided_by_name)
      : null,
  ]
    .filter((x) => x !== null)
    .join(" · ");
  const title = cp.name ?? COPY.checkpoint(cp.seq);
  return (
    <div
      data-checkpoint={cp.seq}
      {...(open ? { "data-open": "" } : {})}
      className={`flex flex-col rounded-nested px-[12px] py-[10px] ${open ? "bg-sel-bg shadow-[inset_0_0_0_1px_var(--color-stroke)]" : "bg-card shadow-e1"}`}
    >
      <div className="flex items-center gap-[8px]">
        <button
          type="button"
          aria-pressed={cp.starred}
          aria-label={cp.starred ? COPY.unstar : COPY.star}
          disabled={!canRename}
          onClick={onStar}
          className={cp.starred ? "text-espresso" : "text-ink-3"}
        >
          <Icon name="star" size={14} className={cp.starred ? "fill-current" : ""} />
        </button>
        {renaming ? (
          <input
            aria-label={COPY.renameLabel(cp.seq)}
            value={name}
            onChange={(e) => {
              setName(e.target.value);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") onRename(name.trim());
            }}
            onBlur={() => {
              onRename(name.trim());
            }}
            className="flex-1 rounded-sheet bg-nested px-[6px] text-section font-medium"
          />
        ) : (
          <button
            type="button"
            aria-expanded={open}
            onClick={onToggle}
            className="flex-1 text-left text-section font-medium"
          >
            {title}
          </button>
        )}
        {cp.current && (
          <span className="rounded-pill bg-card px-[7px] text-meta font-medium shadow-e1">
            {COPY.current}
          </span>
        )}
        <StatePill cp={cp} />
        {canRename && !renaming && (
          <button
            type="button"
            aria-label={COPY.rename}
            onClick={onStartRename}
            className="text-ink-3 hover:text-ink"
          >
            <Icon name="pencil" size={12} />
          </button>
        )}
        <Icon name={open ? "chevron-down" : "chevron-right"} size={12} className="text-ink-3" />
      </div>
      <span className="text-meta text-ink-3">{meta}</span>
      {cp.name !== null && (
        <span className="text-dense text-ink-2">{COPY.checkpoint(cp.seq)}</span>
      )}
      {cp.summary !== null && <span className="text-dense text-ink-2">{cp.summary}</span>}
      {cp.current && decided !== null && decided.decision === "approved" && (
        <span className="mt-[4px] self-start">
          <Pill variant="green-tint" size="sm">
            {COPY.approvedLine(decided.decided_by_name, time(decided.decided_at))}
          </Pill>
        </span>
      )}
      {decided !== null && decided.decision === "rejected" && (
        <span className="text-dense text-red-ink">
          {COPY.rejectedLine(decided.decided_by_name, decided.reason ?? "")}
        </span>
      )}
    </div>
  );
}

export interface CheckpointDrawerProps {
  target: CheckpointTarget;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The checkpoint opened on arrival (by seq); the newest when absent. */
  initialSeq?: number;
  initialFilter?: CheckpointFilter;
  /** c: the restore dialog held open; d: the rename field held open. */
  initialDialog?: "restore" | "rename" | null;
}

export function CheckpointDrawer({
  target,
  open,
  onOpenChange,
  initialSeq,
  initialFilter = "all",
  initialDialog = null,
}: CheckpointDrawerProps): JSX.Element {
  const now = useNow();
  const session = useSession();
  const actor: Actor =
    session.user === null ? { kind: "system" } : { kind: "human", name: session.user.displayName };
  const [filter, setFilter] = useState<CheckpointFilter>(initialFilter);
  const history = useCheckpointHistory(target, filter);
  const items = history.data?.items ?? [];
  const [chosen, setChosen] = useState<number | null>(initialSeq ?? null);
  const selectedSeq = chosen ?? items[0]?.seq ?? null;
  const selected = items.find((c) => c.seq === selectedSeq) ?? null;
  const detail = useCheckpoint(
    selected?.id ?? null,
    selected?.current === false && selected.status !== "proposed" ? "current" : "previous",
  );
  const writes = useCheckpointWrites();
  const [busy, setBusy] = useState(false);
  const [restoring, setRestoring] = useState(initialDialog === "restore");
  const [renaming, setRenaming] = useState<number | null>(
    initialDialog === "rename" ? (initialSeq ?? null) : null,
  );
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveName, setSaveName] = useState("");
  const queryClient = useQueryClient();
  const create = useMutation({
    ...checkpointCreateMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [{ _id: "checkpointHistory" }] });
    },
  });
  const nextSeq = Math.max(0, ...items.map((c) => c.seq)) + 1;

  const run = async (
    write: () => Promise<CheckpointItemOut>,
    done: (cp: CheckpointItemOut) => string,
  ): Promise<void> => {
    setBusy(true);
    try {
      const cp = await write();
      toast.show({ kind: "success", text: done(cp) });
    } catch {
      toast.show({ kind: "error", text: COPY.toasts.failed });
    } finally {
      setBusy(false);
    }
  };

  const canApprove =
    selected?.status === "proposed" && selected.allowed_actions.includes("checkpoint.approve");
  const canReject =
    selected?.status === "proposed" && selected.allowed_actions.includes("checkpoint.reject");
  const canRestore =
    selected !== null &&
    !selected.current &&
    selected.status !== "proposed" &&
    selected.allowed_actions.includes("checkpoint.restore");

  const footer =
    selected === null ? undefined : canApprove || canReject ? (
      <div className="flex flex-col gap-[8px]">
        <p className="text-meta text-ink-3">{COPY.approveNote(selected.seq)}</p>
        <div className="flex items-center gap-[8px]">
          {canReject && (
            <Button
              variant="secondary"
              opensDialog
              disabled={busy}
              className="text-red-ink"
              onClick={() => {
                setRejecting(true);
              }}
            >
              {COPY.reject}
            </Button>
          )}
          {canApprove && (
            <HumanAction
              verb="Approve"
              object={COPY.approve}
              actor={actor}
              disabled={busy}
              className="flex-1"
              onClick={() => {
                void run(
                  () => writes.approve(selected),
                  (cp) => COPY.toasts.approved(cp.seq),
                );
              }}
            />
          )}
        </div>
      </div>
    ) : canRestore ? (
      <Button
        variant="secondary"
        opensDialog
        onClick={() => {
          setRestoring(true);
        }}
      >
        {COPY.restore}
      </Button>
    ) : undefined;

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={COPY.title}
      width={480}
      {...(footer === undefined ? {} : { footer })}
    >
      <div className="flex items-center gap-[8px] px-[10px] pt-[10px]">
        <Segmented
          size="small"
          label={COPY.title}
          options={[
            { label: COPY.segments.checkpoints },
            ...(PLANNED_VISIBLE ? [{ label: COPY.segments.assistant, disabled: true }] : []),
          ]}
          active={COPY.segments.checkpoints}
        />
        <span className="flex-1" />
        <Menu
          label={COPY.filter}
          align="end"
          trigger={
            <button
              type="button"
              aria-label={COPY.filter}
              className="inline-flex size-[28px] items-center justify-center rounded-pill bg-card shadow-e1"
            >
              <Icon name="list-filter" size={14} />
            </button>
          }
          sections={[
            (["agent", "named", "all"] as const).map((f) => ({
              label: COPY.filters[f],
              checked: filter === f,
              onSelect: () => {
                setFilter(f);
                setChosen(null);
              },
            })),
          ]}
        />
      </div>
      {history.data === undefined ? (
        <p className="p-[12px] text-meta text-ink-3">{COPY.loading}</p>
      ) : items.length === 0 ? (
        <EmptyState
          icon="history"
          title={COPY.emptyTitle}
          action={
            history.data.allowed_actions.includes("checkpoint.create") ? (
              <Button
                variant="secondary"
                opensDialog
                onClick={() => {
                  setSaving(true);
                }}
              >
                {COPY.save}
              </Button>
            ) : undefined
          }
        >
          {COPY.emptyBody}
        </EmptyState>
      ) : (
        <ul aria-label={COPY.title} className="flex flex-col gap-[8px] p-[10px]">
          {items.map((cp) => (
            // The list item holds the card and, when open, its detail (axe: only li under ul).
            <li key={cp.id} className="flex flex-col">
              <Card
                cp={cp}
                open={cp.seq === selectedSeq}
                now={now}
                renaming={renaming === cp.seq}
                onToggle={() => {
                  setChosen(cp.seq === selectedSeq ? -1 : cp.seq);
                }}
                onStartRename={() => {
                  setRenaming(cp.seq);
                }}
                onRename={(name) => {
                  setRenaming(null);
                  if (name === (cp.name ?? "")) return;
                  void run(
                    () => writes.rename(cp, { name: name === "" ? null : name }),
                    () => name,
                  );
                }}
                onStar={() => {
                  void run(
                    () => writes.rename(cp, { starred: !cp.starred }),
                    (out) => out.name ?? COPY.checkpoint(out.seq),
                  );
                }}
              />
              {cp.seq === selectedSeq && detail.data !== undefined && (
                <Detail detail={detail.data} />
              )}
            </li>
          ))}
        </ul>
      )}
      <Dialog
        open={restoring && selected !== null}
        onOpenChange={(next) => {
          if (!next) setRestoring(false);
        }}
        title={COPY.restoreDialog.title(selected?.seq ?? 0)}
        size="md"
      >
        <p className="text-para text-ink-2">
          {COPY.restoreDialog.body(selected?.seq ?? 0, nextSeq)}
        </p>
        <div className="flex justify-end gap-[8px] pt-[12px]">
          <Button
            variant="secondary"
            onClick={() => {
              setRestoring(false);
            }}
          >
            {COPY.restoreDialog.cancel}
          </Button>
          <Button
            variant="primary"
            disabled={busy || selected === null}
            onClick={() => {
              if (selected === null) return;
              void run(
                () => writes.restore(selected),
                (cp) => COPY.toasts.restored(cp.seq),
              ).then(() => {
                setRestoring(false);
              });
            }}
          >
            {COPY.restoreDialog.restore}
          </Button>
        </div>
      </Dialog>
      <Dialog
        open={rejecting && selected !== null}
        onOpenChange={(next) => {
          if (!next) setRejecting(false);
        }}
        title={COPY.rejectDialog.title}
        size="md"
        dirty={reason !== ""}
      >
        <ValueRow
          kind="paragraph"
          label={COPY.rejectDialog.reason}
          value={reason}
          onChange={setReason}
        />
        <div className="flex justify-end gap-[8px] pt-[12px]">
          <Button
            variant="secondary"
            onClick={() => {
              setRejecting(false);
            }}
          >
            {COPY.rejectDialog.cancel}
          </Button>
          <Button
            variant="destructive"
            disabled={busy || reason.trim() === "" || selected === null}
            onClick={() => {
              if (selected === null) return;
              void run(
                () => writes.reject(selected, reason.trim()),
                (cp) => COPY.toasts.rejected(cp.seq),
              ).then(() => {
                setRejecting(false);
              });
            }}
          >
            {COPY.rejectDialog.reject}
          </Button>
        </div>
      </Dialog>
      <Dialog
        open={saving}
        onOpenChange={(next) => {
          if (!next) setSaving(false);
        }}
        title={COPY.save}
        size="md"
        dirty={saveName !== ""}
      >
        <ValueRow kind="text" label={COPY.rename} value={saveName} onChange={setSaveName} />
        <div className="flex justify-end pt-[12px]">
          <Button
            variant="primary"
            disabled={create.isPending}
            onClick={() => {
              create.mutate(
                {
                  body: {
                    target_type: target.type,
                    target_id: target.id,
                    ...(saveName.trim() === "" ? {} : { name: saveName.trim() }),
                  },
                },
                {
                  onSuccess: () => {
                    setSaving(false);
                  },
                  onError: () => {
                    toast.show({ kind: "error", text: COPY.toasts.failed });
                  },
                },
              );
            }}
          >
            {COPY.save.replace("…", "")}
          </Button>
        </div>
      </Dialog>
    </Drawer>
  );
}
