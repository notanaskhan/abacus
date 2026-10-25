import { type JSX, Suspense, lazy } from "react";
import { FeatureGate } from "../../app-core/flags";
import { VIEWER_OVERLAY, registerOverlay, sourceViewerTarget } from "../../app-core/overlays";

// SHL-08 (P-03-T14; P-03 §5.1): the source viewer drawer on any firm route,
// `?ov=viewer:<evidenceVersionId>[:<matchId>[:<anchor type>:<anchor id>:<anchor ref>[:<figure>
// [:<engagementId>]]]]`.
// Opening pushes history, so Back closes it; Escape and ✕ close it with `replace`. The viewer is
// its own chunk, loaded only when the drawer opens, and only while `evidence.viewer_v1` is on.

const ViewerDrawer = lazy(async () => ({
  default: (await import("../../screens/SHL-08/ViewerDrawer")).ViewerDrawer,
}));

function ViewerOverlay({
  args,
  close,
}: {
  args: string[];
  close: () => void;
}): JSX.Element | null {
  const target = sourceViewerTarget(args);
  if (target === undefined) return null;
  return (
    <FeatureGate flag="evidence.viewer_v1">
      <Suspense fallback={null}>
        <ViewerDrawer
          target={{
            versionId: target.evidenceVersionId,
            matchId: target.matchId ?? null,
            anchor: target.anchor ?? null,
            figure: target.figure ?? null,
            engagementId: target.engagementId ?? null,
          }}
          open
          onOpenChange={(open) => {
            if (!open) close();
          }}
        />
      </Suspense>
    </FeatureGate>
  );
}

registerOverlay(VIEWER_OVERLAY, {
  layer: "drawer",
  render: ({ ref, close }) => <ViewerOverlay args={ref.args} close={close} />,
});

export { VIEWER_OVERLAY };
