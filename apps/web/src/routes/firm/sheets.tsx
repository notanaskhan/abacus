import { Suspense, lazy } from "react";
import { type OverlayRenderProps, registerOverlay } from "../../app-core/overlays";

// The sheets any firm route can open by `?ov=`: SIG-02 envelope (N-02-T21,
// `?ov=envelope:<envelopeId>`). Only the registration loads with the app (the firm's 250 KB initial budget, FE-17); the flag
// gates and the screens are one chunk, loaded when a sheet opens (`sheets-host.tsx`).

const Host = lazy(() => import("./sheets-host"));

function render(props: OverlayRenderProps) {
  return (
    <Suspense fallback={null}>
      <Host {...props} />
    </Suspense>
  );
}

registerOverlay("envelope", { layer: "modal", render });
