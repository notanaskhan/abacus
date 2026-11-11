// A-07-T47: AUD-25 live inside the cockpit: the polled archive state, the lock action and the
// shell's step-up. Loaded on first open (its own chunk), so the cockpit carries none of it.
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
  if (archive.data === undefined) return null;
  return (
    <>
      <ArchiveLive
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
