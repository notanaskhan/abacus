import { Suspense, lazy } from "react";
import { type OverlayRenderProps, registerOverlay } from "../../app-core/overlays";

// A-06-T12: the Evaluation overlays (`?ov=convert`, `?ov=send-entries`, `?ov=send-fs-draft`), one
// small chunk loaded when one opens, planned until AUD-15, AUD-16 and AUD-20 land.

const Planned = lazy(async () => ({
  default: (await import("../../screens/evaluation")).PlannedSheet,
}));

function render(props: OverlayRenderProps) {
  return (
    <Suspense fallback={null}>
      <Planned {...props} />
    </Suspense>
  );
}

for (const key of ["convert", "send-entries", "send-fs-draft"]) {
  registerOverlay(key, { layer: "modal", render });
}
