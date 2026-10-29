import { Suspense, lazy } from "react";
import { FeatureGate } from "../../app-core/flags";
import { registerOverlay } from "../../app-core/overlays";

// SHL-10 (P-04-T41): the approve-agent-output sheet on any firm route, `?ov=approve:<proposalRef>`.
// Opening pushes history, so Back closes it; Escape and ✕ close it with `replace`. Its own chunk,
// loaded on open, and only while `review.grammar_api` is on (the C3 routes answer 404 off).

export const APPROVE_OVERLAY = "approve";

const ApproveSheet = lazy(async () => ({
  default: (await import("../../screens/SHL-10")).ApproveSheet,
}));

registerOverlay(APPROVE_OVERLAY, {
  layer: "modal",
  render: ({ ref, close }) => {
    const proposalRef = ref.args[0];
    return proposalRef === undefined ? null : (
      <FeatureGate flag="review.grammar_api">
        <Suspense fallback={null}>
          <ApproveSheet
            proposalRef={proposalRef}
            open
            onOpenChange={(open) => {
              if (!open) close();
            }}
          />
        </Suspense>
      </FeatureGate>
    );
  },
});
