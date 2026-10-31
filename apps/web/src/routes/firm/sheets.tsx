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
// P-04-T43: SHL-16 `?ov=checkpoints:<target_type>:<target_id>`, the O2 drawer.
registerOverlay("checkpoints", { layer: "drawer", render });
// P-04-T48: SHL-12 `?ov=signoff:<target_type>:<target_id>[:<level>]`, the O3 sheet.
registerOverlay("signoff", { layer: "modal", render });
// P-04-T50: SHL-11 `?ov=decision:<cardId>`, the O3 decision sheet.
registerOverlay("decision", { layer: "modal", render });
// P-04-T49 (S20 wire-up): SHL-12 f `?ov=signoffs:<target_type>:<id>,<id>,…:<level>`, the bulk sheet.
registerOverlay("signoffs", { layer: "modal", render });
// T-01-T15 follow-up (DEC-1288): TAX-09 `?ov=engine-sync:<returnId>`, the return's engine sync.
registerOverlay("engine-sync", { layer: "modal", render });
