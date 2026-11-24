import { Suspense, lazy } from "react";
import { type OverlayRenderProps, registerOverlay } from "../../app-core/overlays";

// T-06-T45 (DEC-5937): AUD-38's O3 hand-off sheet over AUD-06, `?ov=tax-handoff:<auditWorkItemId>`,
// loaded when it opens (behind `tax.tb_handoff`: the reads 404 with the flag off).

const Sheet = lazy(async () => ({ default: (await import("../../screens/AUD-38")).AUD38 }));

registerOverlay("tax-handoff", {
  layer: "modal",
  render: ({ ref, close }: OverlayRenderProps) => (
    <Suspense fallback={null}>
      <Sheet workItemId={ref.args[0] ?? ""} close={close} />
    </Suspense>
  ),
});
