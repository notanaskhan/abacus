import { Suspense, lazy } from "react";
import { FeatureGate } from "../../app-core/flags";
import { registerOverlay } from "../../app-core/overlays";

// SIG-02 (N-02-T21): the envelope builder on any firm route, `?ov=envelope:<envelopeId>`. Opening
// pushes history, so Back closes it. Its own chunk, loaded on open, and only while
// `signatures.envelopes` is on.

export const ENVELOPE_OVERLAY = "envelope";

const EnvelopeBuilder = lazy(async () => ({
  default: (await import("../../screens/SIG-02")).EnvelopeBuilder,
}));

registerOverlay(ENVELOPE_OVERLAY, {
  layer: "modal",
  render: ({ ref, close }) => {
    const envelopeId = ref.args[0];
    return envelopeId === undefined ? null : (
      <FeatureGate flag="signatures.envelopes">
        <Suspense fallback={null}>
          <EnvelopeBuilder
            envelopeId={envelopeId}
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
