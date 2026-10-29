import { Suspense, lazy } from "react";
import { type OverlayRenderProps, registerOverlay } from "../../app-core/overlays";

// The O3/O4 sheets any firm route can open by `?ov=`: SHL-10 approve (P-04-T41,
// `?ov=approve:<proposalRef>`) and SIG-02 envelope (N-02-T21, `?ov=envelope:<envelopeId>`). Only
// the two registrations load with the app (the firm's 250 KB initial budget, FE-17); the flag
// gates and the screens are one chunk, loaded when a sheet opens (`sheets-host.tsx`).

const Host = lazy(() => import("./sheets-host"));

function render(props: OverlayRenderProps) {
  return (
    <Suspense fallback={null}>
      <Host {...props} />
    </Suspense>
  );
}

registerOverlay("approve", { layer: "modal", render });
registerOverlay("envelope", { layer: "modal", render });
