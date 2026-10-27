import type {
  AuditEngagementStatus,
  EngagementExportOut,
  ReleaseRecordIn,
} from "@abacus/api-client";
import {
  auditArchiveRecordMutation,
  auditPhaseMutation,
  auditReleaseRecordMutation,
} from "@abacus/api-client/query";
import { Button, Dialog, RadioGroup, ValueRow, status, toast } from "@abacus/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { errorCode, needsStepUp, useExportHistory } from "./exports";
import { AUDIT_MESSAGES } from "./messages";
import { RevealStepUp } from "./reveal";

// Record mode (A-01-T24; A-01 §3.5, DV-4): O3 confirm dialogs in local state, one per record. A
// named person records the audit's phase, the report's external release and the archive in the
// firm's own tool (against a ready final-binder export); none is offered to the agent (the
// routes refuse it, INV-1). Release and archive need a fresh second factor: a 403 naming
// `mfa_required` opens the shell's step-up. A refusal from the contract reads in words (audits-cockpit §6).

const R = AUDIT_MESSAGES.record;
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

/** The phases a person may record, in order (C2 `audit_engagement`; the server decides moves). */
export const RECORDABLE: readonly AuditEngagementStatus[] = [
  "planning",
  "fieldwork",
  "in_review",
  "completion",
  "ready_to_release",
];

export type RecordKind = "phase" | "release" | "archive";

function phaseWord(code: AuditEngagementStatus): string {
  return status("audit_engagement", code).label;
}

/** The record routes answer a stale second factor with 403 `facts.reason = mfa_required`
 * (A-01-T23, DEC-547): only that opens the step-up; a role, independence or archived refusal is
 * a plain 403 and reads as a problem. */
function recordStepUp(error: unknown): boolean {
  return needsStepUp(error);
}

function refusal(error: unknown): string {
  const code = errorCode(error);
  return (code === null ? undefined : R.refusals[code]) ?? R.problem;
}

function useRefresh(): () => void {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({
      predicate: (q) => {
        const id = (q.queryKey[0] as { _id?: string } | undefined)?._id ?? "";
        return id === "auditCockpit" || id === "listExports";
      },
    });
  };
}

function Frame({
  open,
  onOpenChange,
  title,
  confirm,
  busy,
  ready,
  problem,
  onConfirm,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  confirm: string;
  busy: boolean;
  ready: boolean;
  problem: string | null;
  onConfirm: () => void;
  children: ReactNode;
}): JSX.Element {
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={title}>
      <div className="flex flex-col gap-[12px]">
        {children}
        {problem !== null && (
          <p role="alert" className="text-meta text-red-ink">
            {problem}
          </p>
        )}
        <div className="flex justify-end gap-[8px]">
          <Button
            variant="secondary"
            onClick={() => {
              onOpenChange(false);
            }}
          >
            {R.cancel}
          </Button>
          <Button variant="primary" disabled={busy || !ready} onClick={onConfirm}>
            {confirm}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

interface DialogProps {
  workItemId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** "Record phase…": the next phase, and an optional reason. */
export function PhaseRecordDialog({
  workItemId,
  open,
  onOpenChange,
  current,
}: DialogProps & { current: AuditEngagementStatus }): JSX.Element {
  const next = RECORDABLE[RECORDABLE.indexOf(current) + 1];
  const [to, setTo] = useState<AuditEngagementStatus | undefined>(next);
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [stepUp, setStepUp] = useState(false);
  const refresh = useRefresh();
  const record = useMutation({ ...auditPhaseMutation(), onSettled: refresh });
  const submit = async (): Promise<void> => {
    if (to === undefined) return;
    setProblem(null);
    try {
      await record.mutateAsync({
        path: { work_item_id: workItemId },
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: { to, ...(reason.trim() === "" ? {} : { reason: reason.trim() }) },
      });
      onOpenChange(false);
      toast.show({ text: R.recorded });
    } catch (error) {
      if (recordStepUp(error)) setStepUp(true);
      else setProblem(refusal(error));
    }
  };
  return (
    <>
      <Frame
        open={open}
        onOpenChange={onOpenChange}
        title={R.phase.title}
        confirm={R.phase.confirm}
        busy={record.isPending}
        ready={to !== undefined}
        problem={problem}
        onConfirm={() => void submit()}
      >
        <RadioGroup
          label={R.phase.to}
          options={RECORDABLE.map((p) => ({ value: p, label: phaseWord(p) }))}
          {...(to === undefined ? {} : { value: to })}
          onChange={(value) => {
            setTo(value as AuditEngagementStatus);
          }}
        />
        <ValueRow kind="text" label={R.phase.reason} value={reason} onChange={setReason} />
      </Frame>
      <RevealStepUp open={stepUp} onOpenChange={setStepUp} />
    </>
  );
}

/** "Record release…": the external release date and the report kind (interim G8). */
export function ReleaseRecordDialog({ workItemId, open, onOpenChange }: DialogProps): JSX.Element {
  const [on, setOn] = useState("");
  const [kind, setKind] = useState<ReleaseRecordIn["report_kind"]>("opinion");
  const [problem, setProblem] = useState<string | null>(null);
  const [stepUp, setStepUp] = useState(false);
  const refresh = useRefresh();
  const record = useMutation({ ...auditReleaseRecordMutation(), onSettled: refresh });
  const submit = async (): Promise<void> => {
    setProblem(null);
    try {
      await record.mutateAsync({
        path: { work_item_id: workItemId },
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: { report_released_on: on, report_kind: kind },
      });
      onOpenChange(false);
      toast.show({ text: R.recorded });
    } catch (error) {
      if (recordStepUp(error)) setStepUp(true);
      else setProblem(refusal(error));
    }
  };
  return (
    <>
      <Frame
        open={open}
        onOpenChange={onOpenChange}
        title={R.release.title}
        confirm={R.release.confirm}
        busy={record.isPending}
        ready={ISO_DAY.test(on)}
        problem={problem}
        onConfirm={() => void submit()}
      >
        <ValueRow
          kind="text"
          label={R.release.on}
          placeholder={R.release.datePlaceholder}
          value={on}
          onChange={setOn}
          {...(on === "" || ISO_DAY.test(on) ? {} : { error: R.release.dateInvalid })}
        />
        <RadioGroup
          label={R.release.kind}
          value={kind}
          options={[
            { value: "opinion", label: R.release.opinion },
            { value: "no_report", label: R.release.noReport },
          ]}
          onChange={(value) => {
            setKind(value as ReleaseRecordIn["report_kind"]);
          }}
        />
      </Frame>
      <RevealStepUp open={stepUp} onOpenChange={setStepUp} />
    </>
  );
}

function finalReady(items: readonly EngagementExportOut[]): EngagementExportOut[] {
  return items.filter((e) => e.kind === "final_binder" && e.status === "ready");
}

/** "Record archive…": a ready final-binder export and the firm tool's reference (interim G9). */
export function ArchiveRecordDialog({ workItemId, open, onOpenChange }: DialogProps): JSX.Element {
  const history = useExportHistory(workItemId, open);
  const ready = finalReady(history.data?.items ?? []);
  const [chosen, setChosen] = useState<string | undefined>(undefined);
  const [reference, setReference] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [stepUp, setStepUp] = useState(false);
  const refresh = useRefresh();
  const record = useMutation({ ...auditArchiveRecordMutation(), onSettled: refresh });
  const exportId = chosen ?? ready[0]?.id;
  const submit = async (): Promise<void> => {
    if (exportId === undefined) return;
    setProblem(null);
    try {
      await record.mutateAsync({
        path: { work_item_id: workItemId },
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: { export_id: exportId, firm_tool_ref: reference.trim() },
      });
      onOpenChange(false);
      toast.show({ text: R.recorded });
    } catch (error) {
      if (recordStepUp(error)) setStepUp(true);
      else setProblem(refusal(error));
    }
  };
  return (
    <>
      <Frame
        open={open}
        onOpenChange={onOpenChange}
        title={R.archive.title}
        confirm={R.archive.confirm}
        busy={record.isPending}
        ready={exportId !== undefined && reference.trim() !== ""}
        problem={problem}
        onConfirm={() => void submit()}
      >
        {ready.length === 0 ? (
          <p className="text-meta text-ink-3">{R.archive.none}</p>
        ) : (
          <RadioGroup
            label={R.archive.exportLabel}
            {...(exportId === undefined ? {} : { value: exportId })}
            options={ready.map((e) => ({
              value: e.id,
              label: `${e.requested_by.display_name} · ${e.ready_at?.slice(0, 10) ?? ""}`,
            }))}
            onChange={setChosen}
          />
        )}
        <ValueRow
          kind="text"
          label={R.archive.reference}
          value={reference}
          onChange={(next) => {
            setReference(next.slice(0, 120));
          }}
        />
      </Frame>
      <RevealStepUp open={stepUp} onOpenChange={setStepUp} />
    </>
  );
}

/** The one record dialog open at a time. */
export function RecordDialog({
  kind,
  workItemId,
  current,
  onClose,
}: {
  kind: RecordKind | null;
  workItemId: string;
  current: AuditEngagementStatus;
  onClose: () => void;
}): JSX.Element | null {
  const change = (open: boolean): void => {
    if (!open) onClose();
  };
  if (kind === "phase") {
    return (
      <PhaseRecordDialog workItemId={workItemId} current={current} open onOpenChange={change} />
    );
  }
  if (kind === "release") {
    return <ReleaseRecordDialog workItemId={workItemId} open onOpenChange={change} />;
  }
  if (kind === "archive") {
    return <ArchiveRecordDialog workItemId={workItemId} open onOpenChange={change} />;
  }
  return null;
}
