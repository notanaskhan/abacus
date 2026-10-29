import { type JSX, Suspense, lazy } from "react";
import { FeatureGate } from "../../app-core/flags";
import type { OverlayRenderProps } from "../../app-core/overlays";

// The sheets `sheets.tsx` registers, loaded when one opens: each behind its flag
// (`signatures.envelopes` for SIG-02) and its own screen chunk.

const EnvelopeBuilder = lazy(async () => ({
  default: (await import("../../screens/SIG-02")).EnvelopeBuilder,
}));

export default function SheetsHost({ ref, close }: OverlayRenderProps): JSX.Element | null {
  const id = ref.args[0];
  if (id === undefined) return null;
  const onOpenChange = (open: boolean): void => {
    if (!open) close();
  };
  return (
    <FeatureGate flag="signatures.envelopes">
      <Suspense fallback={null}>
        <EnvelopeBuilder envelopeId={id} open onOpenChange={onOpenChange} />
      </Suspense>
    </FeatureGate>
  );
}
