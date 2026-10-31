import { type JSX, Suspense, lazy } from "react";
import { FeatureGate } from "../../app-core/flags";
import type { OverlayRenderProps } from "../../app-core/overlays";

// The sheets `sheets.tsx` registers, loaded when one opens: each behind its flag
// (`review.grammar_api` for SHL-10, SHL-11 and SHL-12, `review.checkpoints` for SHL-16,
// `signatures.envelopes` for SIG-02, `tax.returns_v1` for TAX-09's engine sync) and its own
// screen chunk.

const ApproveSheet = lazy(async () => ({
  default: (await import("../../screens/SHL-10")).ApproveSheet,
}));
const CheckpointDrawer = lazy(async () => ({
  default: (await import("../../screens/SHL-16")).CheckpointDrawer,
}));
const SignOffSheet = lazy(async () => ({
  default: (await import("../../screens/SHL-12")).SignOffSheet,
}));
const EngineSyncLayer = lazy(async () => ({
  default: (await import("../../screens/TAX-09")).EngineSyncLayer,
}));
const BulkSignOffSheet = lazy(async () => ({
  default: (await import("../../screens/SHL-12")).BulkSignOffSheet,
}));
const DecisionSheet = lazy(async () => ({
  default: (await import("../../screens/SHL-11")).DecisionSheet,
}));
const EnvelopeBuilder = lazy(async () => ({
  default: (await import("../../screens/SIG-02")).EnvelopeBuilder,
}));

export default function SheetsHost(props: OverlayRenderProps): JSX.Element | null {
  const { ref, close } = props;
  const id = ref.args[0];
  if (id === undefined) return null;
  if (ref.key === "engine-sync") {
    return (
      <FeatureGate flag="tax.returns_v1">
        <Suspense fallback={null}>
          <EngineSyncLayer {...props} />
        </Suspense>
      </FeatureGate>
    );
  }
  const onOpenChange = (open: boolean): void => {
    if (!open) close();
  };
  if (ref.key === "checkpoints") {
    const targetId = ref.args[1];
    if (targetId === undefined) return null;
    return (
      <FeatureGate flag="review.checkpoints">
        <Suspense fallback={null}>
          <CheckpointDrawer target={{ type: id, id: targetId }} open onOpenChange={onOpenChange} />
        </Suspense>
      </FeatureGate>
    );
  }
  if (ref.key === "signoff") {
    const targetId = ref.args[1];
    if (targetId === undefined) return null;
    const level = ref.args[2];
    return (
      <FeatureGate flag="review.grammar_api">
        <Suspense fallback={null}>
          <SignOffSheet
            target={{ type: id, id: targetId }}
            {...(level === undefined ? {} : { level })}
            open
            onOpenChange={onOpenChange}
          />
        </Suspense>
      </FeatureGate>
    );
  }
  if (ref.key === "signoffs") {
    const ids = (ref.args[1] ?? "").split(",").filter((t) => t !== "");
    const level = ref.args[2];
    if (ids.length === 0) return null;
    return (
      <FeatureGate flag="review.grammar_api">
        <Suspense fallback={null}>
          <BulkSignOffSheet
            targets={ids.map((targetId) => ({ type: id, id: targetId }))}
            {...(level === undefined ? {} : { level })}
            open
            onOpenChange={onOpenChange}
          />
        </Suspense>
      </FeatureGate>
    );
  }
  if (ref.key === "decision") {
    return (
      <FeatureGate flag="review.grammar_api">
        <Suspense fallback={null}>
          <DecisionSheet cardId={id} open onOpenChange={onOpenChange} />
        </Suspense>
      </FeatureGate>
    );
  }
  if (ref.key === "approve") {
    return (
      <FeatureGate flag="review.grammar_api">
        <Suspense fallback={null}>
          <ApproveSheet proposalRef={id} open onOpenChange={onOpenChange} />
        </Suspense>
      </FeatureGate>
    );
  }
  return (
    <FeatureGate flag="signatures.envelopes">
      <Suspense fallback={null}>
        <EnvelopeBuilder envelopeId={id} open onOpenChange={onOpenChange} />
      </Suspense>
    </FeatureGate>
  );
}
