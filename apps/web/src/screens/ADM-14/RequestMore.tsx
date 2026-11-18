// "Request more" (G-04-T18, DEC-5639; ADM-14 f; SPEC-680 AC-40, AC-43): Dialog 440 that creates a
// plan request for the partner to approve. ADM-14's "Request more…", ADM-01's "Add seats" helper
// and ADM-02's "Add seats…" open this one dialog, so all three create the same `seats` request.
// The dialog reads the plan (seat total) and the partner approver from the server; a viewer
// without `plan.read`, or a firm with `platform.plan_usage` off, never gets an entry point (the
// callers show it only once `/v1/firm/plan` answers).
import type { PlanRequestIn } from "@abacus/api-client";
import {
  budgetAlertsGetOptions,
  planGetOptions,
  planRequestsCreateMutation,
} from "@abacus/api-client/query";
import { Button, Dialog } from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { COPY as C } from "./copy";

/** The server's reason floor (`PlanRequestIn.reason`, 10 to 500 characters). */
const REASON_MIN = 10;
const REASON_MAX = 500;

export interface RequestMoreDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function RequestMoreDialog({ open, onOpenChange }: RequestMoreDialogProps): JSX.Element {
  const plan = useQuery({ ...planGetOptions(), retry: false });
  const alerts = useQuery({ ...budgetAlertsGetOptions(), retry: false });
  const [reason, setReason] = useState("");
  const [seatsTo, setSeatsTo] = useState<string>("");
  const request = useMutation({
    ...planRequestsCreateMutation(),
    onSuccess: () => {
      setReason("");
      setSeatsTo("");
      onOpenChange(false);
    },
  });
  const total = plan.data?.seats.total;
  const to = seatsTo === "" ? total : Number(seatsTo);
  const ready =
    reason.trim().length >= REASON_MIN &&
    typeof total === "number" &&
    typeof to === "number" &&
    to > total &&
    !request.isPending;
  const approver = alerts.data?.partner_approver;
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={C.request.title}
      action={
        <Button
          variant="primary"
          disabled={!ready}
          onClick={() => {
            if (!ready) return;
            const input: PlanRequestIn = { kind: "seats", reason: reason.trim(), to_value: to };
            request.mutate({
              headers: { "Idempotency-Key": `plan-request-${crypto.randomUUID()}` },
              body: input,
            });
          }}
        >
          {C.request.send}
        </Button>
      }
    >
      <div data-adm14="request" className="flex flex-col gap-[8px] p-[16px] text-[13px]">
        <label className="flex items-center justify-between gap-[8px]">
          <span className="text-ink-2">{C.request.seats}</span>
          <input
            type="number"
            min={total ?? 0}
            value={seatsTo === "" ? String(total ?? "") : seatsTo}
            onChange={(e) => {
              setSeatsTo(e.target.value);
            }}
            className="h-[30px] w-[96px] rounded-input bg-card px-[8px] text-right inset-ring-[0.5px] inset-ring-stroke"
          />
        </label>
        <label className="flex flex-col gap-[4px]">
          <span className="text-ink-2">{C.request.reason}</span>
          <textarea
            value={reason}
            maxLength={REASON_MAX}
            onChange={(e) => {
              setReason(e.target.value);
            }}
            className="min-h-[72px] rounded-input bg-card p-[8px] inset-ring-[0.5px] inset-ring-stroke"
          />
        </label>
        {approver ? (
          <p className="text-[12.5px] text-ink-3">{C.request.approval(approver.display_name)}</p>
        ) : null}
      </div>
    </Dialog>
  );
}
