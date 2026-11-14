// WB-03 a, a2, g (W-02-T21; W-02 §3.6; DEC-4943): the plan card on the run's newest plan version
// (`GET /v1/agent-runs/{id}/plan`): numbered steps, "Data it will read" with code's counts,
// "Writes that need your approval" with the approver, and the owner's Approve plan, Edit plan
// (steps become fields; the server re-validates) and Cancel, each against the version seen. A
// cancelled plan reads one muted line; nothing was read in bulk or written.
import type { RunPlanOut } from "@abacus/api-client";
import {
  approveRunPlanMutation,
  cancelRunPlanMutation,
  editRunPlanMutation,
  runPlanOptions,
} from "@abacus/api-client/query";
import { Button, time as clockTime } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { COPY } from "./copy";

export interface PlanCardViewProps {
  plan: RunPlanOut;
  /** The owner's controls (the server answers 403 to anyone else). */
  canDecide: boolean;
  busy?: boolean;
  timeZone?: string;
  onApprove?: () => void;
  onCancel?: () => void;
  onSaveEdit?: (labels: Readonly<Record<string, string>>) => void;
}

export function PlanCardView({
  plan,
  canDecide,
  busy,
  timeZone = "America/Chicago",
  onApprove,
  onCancel,
  onSaveEdit,
}: PlanCardViewProps): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [labels, setLabels] = useState<Record<string, string>>({});
  if (plan.state === "cancelled") {
    return (
      <p data-plan="cancelled" className="text-[12.5px] text-ink-3">
        {COPY.cancelled(plan.decided_by ?? "", plan.decided_at ? clockTime(plan.decided_at, { tz: timeZone }) : "")}
      </p>
    );
  }
  const open = plan.state === "proposed" || plan.state === "edited";
  return (
    <section data-plan={plan.state} className="rounded-[12px] bg-card p-[12px] shadow-e1">
      <header className="flex items-center gap-[6px]">
        <span className="flex-1 text-[13.5px] font-medium text-ink">{COPY.planTitle}</span>
        {open ? (
          <span className="rounded-pill bg-amber-tint px-[8px] text-[11px] text-amber-ink">
            {COPY.planReady}
          </span>
        ) : null}
      </header>
      <ol className="mt-[8px] flex flex-col gap-[4px] text-[13px] text-ink">
        {plan.steps.map((s, i) => (
          <li key={s.key} className="flex gap-[6px]">
            <span className="w-[16px] text-ink-3 tabular-nums">{i + 1}</span>
            {editing ? (
              <input
                aria-label={COPY.stepLabel(i + 1)}
                defaultValue={s.label}
                onChange={(e) => {
                  setLabels((l) => ({ ...l, [s.key]: e.target.value }));
                }}
                className="h-[26px] flex-1 rounded-[6px] bg-nested px-[6px] text-[13px]"
              />
            ) : (
              <span className="flex-1">{s.label}</span>
            )}
          </li>
        ))}
      </ol>
      {(plan.reads ?? []).length > 0 ? (
        <>
          <h4 className="mt-[10px] text-[11.5px] text-ink-3">{COPY.dataItWillRead}</h4>
          <p data-plan-reads className="text-[12.5px] text-ink-2">
            {(plan.reads ?? []).map((r) => `${r.label} ${r.count.toLocaleString("en-US")}`).join(" · ")}
          </p>
        </>
      ) : null}
      {(plan.writes ?? []).length > 0 ? (
        <>
          <h4 className="mt-[8px] text-[11.5px] text-ink-3">{COPY.writesNeedApproval}</h4>
          <ul data-plan-writes className="text-[12.5px] text-ink-2">
            {(plan.writes ?? []).map((w) => (
              <li key={`${w.step_key}:${w.action}`}>
                {w.label}
                {w.approver_name ? ` · ${w.approver_name}` : ""}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {open && canDecide ? (
        <div className="mt-[10px] flex justify-end gap-[6px]">
          {editing ? (
            <>
              <Button variant="ghost" size="sm" onClick={() => { setEditing(false); setLabels({}); }}>
                {COPY.cancelEdit}
              </Button>
              <Button
                variant="primary"
                size="sm"
                disabled={busy === true}
                onClick={() => {
                  setEditing(false);
                  onSaveEdit?.(labels);
                }}
              >
                {COPY.saveEdit}
              </Button>
            </>
          ) : (
            <>
              <Button variant="ghost" size="sm" onClick={onCancel}>
                {COPY.cancelPlan}
              </Button>
              <Button variant="secondary" size="sm" onClick={() => { setEditing(true); }}>
                {COPY.editPlan}
              </Button>
              <Button variant="primary" size="sm" disabled={busy === true} onClick={onApprove}>
                {COPY.approvePlan}
              </Button>
            </>
          )}
        </div>
      ) : null}
    </section>
  );
}

/** The live card: the plan read and the owner's three decisions against the version seen. */
export function PlanCard({ runId, canDecide }: { runId: string; canDecide: boolean }): JSX.Element | null {
  const client = useQueryClient();
  const path = { run_id: runId };
  const plan = useQuery({ ...runPlanOptions({ path }), retry: false });
  const refresh = () => void client.invalidateQueries({ queryKey: runPlanOptions({ path }).queryKey });
  const approve = useMutation({ ...approveRunPlanMutation(), onSuccess: refresh });
  const edit = useMutation({ ...editRunPlanMutation(), onSuccess: refresh });
  const cancel = useMutation({ ...cancelRunPlanMutation(), onSuccess: refresh });
  const p = plan.data;
  if (p === undefined) return null;
  const headers = () => ({ "Idempotency-Key": crypto.randomUUID() });
  return (
    <PlanCardView
      plan={p}
      canDecide={canDecide}
      busy={approve.isPending || edit.isPending || cancel.isPending}
      onApprove={() => {
        approve.mutate({ path, body: { expected_version: p.version }, headers: headers() });
      }}
      onCancel={() => {
        cancel.mutate({ path, body: { expected_version: p.version }, headers: headers() });
      }}
      onSaveEdit={(labels) => {
        edit.mutate({
          path,
          body: { expected_version: p.version, steps: p.steps.map((s) => s.key), labels },
          headers: headers(),
        });
      }}
    />
  );
}
