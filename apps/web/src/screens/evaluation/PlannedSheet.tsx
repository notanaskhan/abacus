import { Dialog } from "@abacus/ui";
import type { JSX } from "react";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import type { OverlayRenderProps } from "../../app-core/overlays";
import { COPY } from "./copy";

// The Evaluation overlays ahead of their screens (A-06-T12): `?ov=convert:<findingId>` (AUD-15's
// Convert to deficiency or misstatement), `?ov=send-entries:<batchId>` (AUD-16's Send to client…)
// and `?ov=send-fs-draft:<documentId>` (AUD-20's Send draft). Each opens its planned target: "Not
// built yet" in dev, fixture and gallery builds, nothing in production; Back closes it (the
// layer leaves the URL with `replace`).

const OWNER: Record<string, string> = {
  convert: "AUD-15",
  "send-entries": "AUD-16",
  "send-fs-draft": "AUD-20",
};

export function PlannedSheet({ ref, close }: OverlayRenderProps): JSX.Element | null {
  if (!PLANNED_VISIBLE) return null;
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) close();
      }}
      title={COPY.planned}
      description={COPY.plannedBody(OWNER[ref.key] ?? ref.key)}
    >
      <span data-planned-overlay={ref.key} />
    </Dialog>
  );
}
