// A-07-T47: AUD-24 live inside the cockpit: the polled release state, the release action and the
// shell's step-up. Loaded on first open (its own chunk), so the cockpit carries none of it.
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
  if (release.data === undefined) return null;
  return (
    <>
      <IssuanceLive
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
