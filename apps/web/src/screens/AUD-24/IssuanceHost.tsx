// A-07-T47: AUD-24 live inside the cockpit: the polled release state, the release action and the
// shell's step-up. Loaded on first open (its own chunk), so the cockpit carries none of it.
import { governanceListOptions } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { RevealStepUp } from "../../domain/audits";
import { useLiveRelease } from "../../domain/completion-live";
import { IssuanceLive } from "./IssuanceLive";

export function IssuanceHost({
  workItemId,
  onBack,
}: {
  workItemId: string;
  onBack: () => void;
}): JSX.Element | null {
  const { release, action } = useLiveRelease(workItemId);
  // DV-6: the required governance letters, counted by the server per engagement type.
  const gov = useQuery(governanceListOptions({ path: { work_item_id: workItemId } })).data;
  if (release.data === undefined) return null;
  return (
    <>
      <IssuanceLive
        governance={
          gov === undefined ? undefined : { sent: gov.required_sent, total: gov.required_total }
        }
        release={release.data}
        running={action.running}
        problem={action.problem}
        onRelease={() => {
          void action.run();
        }}
        onBack={onBack}
      />
      <RevealStepUp open={action.stepUp} onOpenChange={action.setStepUp} />
    </>
  );
}
