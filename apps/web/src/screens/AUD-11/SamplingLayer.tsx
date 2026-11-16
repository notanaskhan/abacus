import { FullSheet } from "@abacus/ui";
import type { JSX } from "react";
import type { OverlayRenderProps } from "../../app-core/overlays";
import { CockpitCanvasView, useSampleSelectionCanvas } from "../AUD-02";
import { COPY } from "./copy";

/** AUD-11 over a host that is not its cockpit (`?ov=sampling:<workItemId>`; S47, TASK-8338):
 * AUD-12's "Opens AUD-11 · sampling". The same live canvas AUD-02 draws for
 * `?section=sample_selection`, in a full sheet. */
export function SamplingLayer({ ref, close }: OverlayRenderProps): JSX.Element | null {
  const [workItemId] = ref.args;
  if (workItemId === undefined) return null;
  return <Sampling workItemId={workItemId} close={close} />;
}

function Sampling({ workItemId, close }: { workItemId: string; close: () => void }): JSX.Element {
  const canvas = useSampleSelectionCanvas(workItemId);
  return (
    <FullSheet
      open
      onOpenChange={(next) => {
        if (!next) close();
      }}
      title={COPY.title}
    >
      <CockpitCanvasView canvas={canvas} />
    </FullSheet>
  );
}
