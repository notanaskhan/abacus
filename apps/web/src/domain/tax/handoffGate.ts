// The AUD-06 "Hand off to tax…" gate (T-06-T45; AUD-38 d; DEC-5937): with `tax.tb_handoff` on, the
// engagement's eligible return (`…/tax-handoff/targets`) and its preview's gate (`…/preview`).
// Released (or superseded after release): the menu item opens AUD-38; before G8 it is disabled
// with the reason. No target, or the reads unavailable (the assembly is T-06-T59's): no item.
import { handoffPreviewOptions, handoffTargetsOptions } from "@abacus/api-client/query";
import { date } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { useNow } from "../../app-core/clock";
import { useFlag } from "../../app-core/flags";

export const HANDOFF_GATE_COPY = {
  released: (on: string, target: string) => `Final TB released ${on} → ${target}`,
  notReleased: "Available after the report is released (G8)",
};

export interface HandoffGate {
  state: "ready" | "not_released";
  tooltip: string;
  targetId: string;
}

export function useTaxHandoffGate(
  engagementId: string,
  enabled: boolean,
): HandoffGate | undefined {
  const now = useNow();
  const on = useFlag("tax.tb_handoff") === true && enabled;
  const targets = useQuery({
    ...handoffTargetsOptions({ path: { engagement_id: engagementId } }),
    enabled: on,
    retry: false,
  });
  const target = targets.data?.items[0];
  const preview = useQuery({
    ...handoffPreviewOptions({
      path: { engagement_id: engagementId },
      query: { target_work_item_id: target?.target_work_item_id ?? "" },
    }),
    enabled: on && target !== undefined,
    retry: false,
  });
  const p = preview.data;
  if (!on || target === undefined || p === undefined) return undefined;
  if (p.gate === "not_released") {
    return {
      state: "not_released",
      tooltip: HANDOFF_GATE_COPY.notReleased,
      targetId: target.target_work_item_id,
    };
  }
  const released = p.source?.released_on;
  return {
    state: "ready",
    tooltip:
      released == null
        ? (p.target?.return_label ?? target.return_label)
        : HANDOFF_GATE_COPY.released(
            date(released, { now, withYear: true }),
            p.target?.return_label ?? target.return_label,
          ),
    targetId: target.target_work_item_id,
  };
}
