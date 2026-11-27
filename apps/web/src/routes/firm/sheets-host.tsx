import { type JSX, Suspense, lazy } from "react";
import { FeatureGate } from "../../app-core/flags";
import type { OverlayRenderProps } from "../../app-core/overlays";
import { CloseSourceSeam } from "../../app-core/close-seams";

// The sheets `sheets.tsx` registers, loaded when one opens, each in its own screen chunk. SHL-10,
// SHL-11, SHL-12 and SHL-15 need no flag (`review.grammar_api` retired, P-04-T62); the rest stand
// behind theirs (`review.checkpoints` for SHL-16, `signatures.envelopes` for SIG-02,
// the `tax_returns` entitlement for TAX-09's engine sync).

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
const IssueSheet = lazy(async () => ({
  default: (await import("../../screens/SHL-15")).IssueSheet,
}));
const EnvelopeBuilder = lazy(async () => ({
  default: (await import("../../screens/SIG-02")).EnvelopeBuilder,
}));
const ConsolidatedTbLayer = lazy(async () => ({
  default: (await import("../../screens/AUD-33")).ConsolidatedTbLayer,
}));
const ProvenanceLayer = lazy(async () => ({
  default: (await import("../../screens/SHL-09")).ProvenanceLayer,
}));
const IntegrationLayer = lazy(async () => ({
  default: (await import("../../screens/WB-11/live")).IntegrationLayer,
}));
const RowDrawerLayer = lazy(async () => ({
  default: (await import("../../screens/SHT-01/RowDrawer")).RowDrawerLayer,
}));
const ColumnLayer = lazy(async () => ({
  default: (await import("../../screens/SHT-02")).ColumnLayer,
}));
const SamplingLayer = lazy(async () => ({
  default: (await import("../../screens/AUD-11/SamplingLayer")).SamplingLayer,
}));

export default function SheetsHost(props: OverlayRenderProps): JSX.Element | null {
  const { ref, close } = props;
  const id = ref.args[0];
  if (id === undefined) return null;
  if (ref.key === "consolidated-tb") {
    // A-09-T15: AUD-33 stands behind the group audit entitlement, as its screen does.
    return (
      <FeatureGate entitlement="group_audit">
        <Suspense fallback={null}>
          <ConsolidatedTbLayer {...props} />
        </Suspense>
      </FeatureGate>
    );
  }
  if (ref.key === "integration") {
    // S47 (TASK-8338): the API answers 404 with `integrations.connect_v1` off.
    return (
      <Suspense fallback={null}>
        <IntegrationLayer {...props} />
      </Suspense>
    );
  }
  if (ref.key === "sampling") {
    // S47 (TASK-8338): the canvas draws `sampling.sample_sets` off itself (C-20).
    return (
      <Suspense fallback={null}>
        <SamplingLayer {...props} />
      </Suspense>
    );
  }
  if (ref.key === "column") {
    // K-03-T23: the column writes answer 501 until the columns service (K-03-T24).
    return (
      <Suspense fallback={null}>
        <ColumnLayer {...props} />
      </Suspense>
    );
  }
  if (ref.key === "row") {
    // K-03-T22: the API answers 404 with `sheets.enabled` off.
    return (
      <Suspense fallback={null}>
        <RowDrawerLayer {...props} />
      </Suspense>
    );
  }
  if (ref.key === "provenance") {
    return (
      <Suspense fallback={null}>
        <ProvenanceLayer {...props} />
      </Suspense>
    );
  }
  if (ref.key === "engine-sync") {
    return (
      <FeatureGate entitlement="tax_returns">
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
      <CloseSourceSeam overlay="signoff" targetType={id} targetId={targetId}>
        <Suspense fallback={null}>
          <SignOffSheet
            target={{ type: id, id: targetId }}
            {...(level === undefined ? {} : { level })}
            open
            onOpenChange={onOpenChange}
          />
        </Suspense>
      </CloseSourceSeam>
    );
  }
  if (ref.key === "signoffs") {
    const ids = (ref.args[1] ?? "").split(",").filter((t) => t !== "");
    const level = ref.args[2];
    if (ids.length === 0) return null;
    return (
      <Suspense fallback={null}>
        <BulkSignOffSheet
          targets={ids.map((targetId) => ({ type: id, id: targetId }))}
          {...(level === undefined ? {} : { level })}
          open
          onOpenChange={onOpenChange}
        />
      </Suspense>
    );
  }
  if (ref.key === "decision") {
    return (
      <Suspense fallback={null}>
        <DecisionSheet cardId={id} open onOpenChange={onOpenChange} />
      </Suspense>
    );
  }
  if (ref.key === "issue") {
    return (
      <Suspense fallback={null}>
        <IssueSheet args={ref.args} open onOpenChange={onOpenChange} />
      </Suspense>
    );
  }
  if (ref.key === "approve") {
    return (
      <CloseSourceSeam overlay="approve" targetType={ref.args[1]} targetId={id}>
        <Suspense fallback={null}>
          <ApproveSheet proposalRef={id} open onOpenChange={onOpenChange} />
        </Suspense>
      </CloseSourceSeam>
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
