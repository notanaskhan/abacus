import type { JSX } from "react";
import { useOverlays } from "../../app-core/overlay-host";
import { AUD12Live } from "./live";
import { exceptionOverlay, samplingOverlay } from "./links";

// AUD-12 live host (TASK-8354): Raise exception… opens SHL-15 on the test; Expand testing… opens
// AUD-11 on the audit's work item, where expansions are requested and approved.
export function JeTestingPage({
  auditId,
  jeTestId,
}: {
  auditId: string;
  jeTestId: string;
}): JSX.Element {
  const overlays = useOverlays();
  return (
    <div className="bg-shell p-[12px]">
      <AUD12Live
        jeTestId={jeTestId}
        onRaise={() => {
          const ref = exceptionOverlay(jeTestId);
          overlays.open(ref.key, ...ref.args);
        }}
        onExpand={() => {
          const ref = samplingOverlay(auditId);
          overlays.open(ref.key, ...ref.args);
        }}
      />
    </div>
  );
}
