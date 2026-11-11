// A-07-T47: AUD-25 live inside the cockpit: the polled archive state, the lock action and the
// shell's step-up. Loaded on first open (its own chunk), so the cockpit carries none of it.
import { governanceListOptions } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { RevealStepUp } from "../../domain/audits";
import { useLiveArchive } from "../../domain/completion-live";
import { ArchiveLive } from "./ArchiveLive";

export function ArchiveHost({
  workItemId,
  onBack,
}: {
  workItemId: string;
  onBack: () => void;
}): JSX.Element | null {
  const { archive, action } = useLiveArchive(workItemId);
  // DV-6: the required governance letters, counted by the server per engagement type.
  const gov = useQuery(governanceListOptions({ path: { work_item_id: workItemId } })).data;
  if (archive.data === undefined) return null;
  return (
    <>
      <ArchiveLive
        governance={
          gov === undefined ? undefined : { sent: gov.required_sent, total: gov.required_total }
        }
        archive={archive.data}
        running={action.running}
        problem={action.problem}
        thenRollForward={action.thenRollForward}
        onThenRollForward={action.setThenRollForward}
        onLock={() => {
          void action.run();
        }}
        onBack={onBack}
      />
      <RevealStepUp open={action.stepUp} onOpenChange={action.setStepUp} />
    </>
  );
}
