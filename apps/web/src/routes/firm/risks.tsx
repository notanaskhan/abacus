import { Suspense, lazy } from "react";
import { type OverlayRenderProps, registerOverlay } from "../../app-core/overlays";

// A-04-T20: AUD-08's O2 rationale drawer, `?ov=risk:<code>`, loaded when it opens.

const Host = lazy(async () => ({
  default: (await import("../../screens/AUD-08")).RiskDrawerHost,
}));

registerOverlay("risk", {
  layer: "drawer",
  render: (props: OverlayRenderProps) => (
    <Suspense fallback={null}>
      <Host {...props} />
    </Suspense>
  ),
});
