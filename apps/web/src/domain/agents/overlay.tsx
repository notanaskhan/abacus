import { useOverlays } from "../../app-core/overlay-host";
import { RUN_TRACE_OVERLAY } from "./links";

/** Open a run's trace as the page's drawer (WB-09; routes/firm/run-trace.tsx registers it).
 * Pushes history, so Back closes it. */
export function useOpenTrace(): (runId: string) => void {
  const { open } = useOverlays();
  return (runId: string) => {
    open(RUN_TRACE_OVERLAY, runId);
  };
}
