import { Suspense, lazy } from "react";
import { type OverlayRenderProps, registerOverlay } from "../../app-core/overlays";

// A-06-T12: the Evaluation overlays (`?ov=convert`, `?ov=send-entries`, `?ov=send-fs-draft`), one
// small chunk loaded when one opens, planned until AUD-15 and AUD-20 land (AUD-16's O3 is live).

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

// A-06-T22: AUD-16's O3 replaces its planned sheet.
const SendEntries = lazy(async () => ({
  default: (await import("../../screens/AUD-16")).SendEntriesSheet,
}));
registerOverlay("send-entries", {
  layer: "modal",
  render: (props: OverlayRenderProps) => (
    <Suspense fallback={null}>
      <SendEntries {...props} />
    </Suspense>
  ),
});

for (const key of ["convert", "send-fs-draft"]) {
  registerOverlay(key, { layer: "modal", render });
}
