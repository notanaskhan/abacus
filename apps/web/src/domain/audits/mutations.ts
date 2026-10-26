// The audits domain's writes (A-01 §5.2). Auto mode (AUD-02 f, A-01-T31; DEC-405): the switch in
// the audit bar and its confirm, over `PUT /v1/engagements/{engagement_id}/auto-mode`, which
// P-10-T39 serves (ADR-186 §6, DEC-50). The route is not in the OpenAPI document yet, so this
// names its path on the generated `client` (the precedent is domain/portal/sign-in.ts) with the
// body P-10's API table gives, `{enabled, confirmed: true}`; fixture mode answers it from
// fixtures/scenarios/AUD-02.ts. When P-10-T39 lands, the server reports the
// `engagement_run.auto_mode` capability and the switch renders live with no change here.
//
// A refusal is any 403 or 409 (a real firm in Season 1, or the policy), read from the response
// status rather than a code, so whatever fixed code P-10-T39 chooses needs no A-01 change.

import type { AuditCockpitOut } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { auditCockpitQueryKey } from "@abacus/api-client/query";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { Action } from "../../app-core/actions.gen";
import { useCan } from "../../app-core/can";

/** The `/v1/me` capability the switch waits for (P-10-T39 adds it to the matrix and so to
 * actions.gen.ts; until then the server never reports it and the switch is absent live). */
export const AUTO_MODE_CAPABILITY = "engagement_run.auto_mode";

/** P-10's route (docs/plan/epics/P-10.md, API table; P-10-T39). */
export const AUTO_MODE_PATH = "/v1/engagements/{engagement_id}/auto-mode";

/** The request body P-10-T39 takes: the new value and the person's confirmation. */
export interface AutoModeIn {
  enabled: boolean;
  confirmed: true;
}

export type AutoModeResult =
  | { kind: "saved"; enabled: boolean }
  | { kind: "refused"; code: string | null }
  | { kind: "failed" };

const REFUSED = new Set([403, 409]);

/** `PUT /v1/engagements/{id}/auto-mode`: the one place the switch writes. */
export async function putAutoMode(
  engagementId: string,
  enabled: boolean,
): Promise<AutoModeResult> {
  const body: AutoModeIn = { enabled, confirmed: true };
  const result = await client.put<{ 200: unknown }, Record<number, { detail?: unknown } | null>>({
    url: AUTO_MODE_PATH,
    path: { engagement_id: engagementId },
    body,
    headers: { "Content-Type": "application/json" },
    throwOnError: false,
  });
  if (result.error === undefined) return { kind: "saved", enabled };
  const status = result.response?.status ?? 0;
  if (!REFUSED.has(status)) return { kind: "failed" };
  const detail = result.error?.detail;
  return { kind: "refused", code: typeof detail === "string" ? detail : null };
}

/** idle: the saved value shows; asking: the confirm is open; refused: it shows the refusal. */
export type AutoModeStep = "idle" | "asking" | "refused";

export interface AutoModeControl {
  /** The person holds `engagement_run.auto_mode` on this engagement (`/v1/me`). */
  allowed: boolean;
  /** What the switch shows: pressed while the confirm is open. */
  on: boolean;
  step: AutoModeStep;
  saving: boolean;
  /** The switch was pressed: turning on asks first; turning off writes at once. */
  press: (next: boolean) => void;
  /** Cancel, Escape or the scrim: the switch goes back to the saved value. */
  cancel: () => void;
  /** "Turn on". */
  confirm: () => void;
}

/** The Auto mode switch and its confirm for one audit cockpit. */
export function useAutoMode(
  cockpit: Pick<AuditCockpitOut, "work_item_id" | "engagement_id" | "audit_bar">,
  initial: AutoModeStep = "idle",
): AutoModeControl {
  // Not in actions.gen.ts until P-10-T39's matrix row; the answer is the server's either way.
  const allowed = useCan(AUTO_MODE_CAPABILITY as Action, { engagementId: cockpit.engagement_id });
  const queryClient = useQueryClient();
  const [step, setStep] = useState<AutoModeStep>(initial);
  const [saving, setSaving] = useState(false);
  const saved = cockpit.audit_bar.auto_mode ?? false;

  const write = async (enabled: boolean): Promise<void> => {
    setSaving(true);
    const result = await putAutoMode(cockpit.engagement_id, enabled);
    setSaving(false);
    if (result.kind === "saved") {
      queryClient.setQueryData<AuditCockpitOut>(
        auditCockpitQueryKey({ path: { work_item_id: cockpit.work_item_id } }),
        (old) =>
          old === undefined
            ? old
            : { ...old, audit_bar: { ...old.audit_bar, auto_mode: enabled } },
      );
      setStep("idle");
      return;
    }
    // A refused turn-on keeps the confirm open with the reason; anything else leaves it as saved.
    setStep(result.kind === "refused" && enabled ? "refused" : "idle");
  };

  return {
    allowed,
    on: step === "idle" ? saved : true,
    step,
    saving,
    press: (next) => {
      if (next) setStep("asking");
      else void write(false);
    },
    cancel: () => {
      setStep("idle");
    },
    confirm: () => {
      void write(true);
    },
  };
}
