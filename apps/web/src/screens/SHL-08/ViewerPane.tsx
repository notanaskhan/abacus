// SHL-08 on its second host, the T2 dock "Viewer" pane (P-03-T14; AC3.3): the compact evidence
// bar [− Fit + ⟳] ["2 / 3"] with the file name and Download only in its ⋯ menu. The pane's target
// is local state seeded from the selected row's citation (P-03 §5.1); a host re-targets it by
// passing another anchor, and the pane follows without closing.

import { MatchScope } from "@abacus/ui";
import type { JSX } from "react";
import {
  EvidenceViewerBody,
  type EvidenceViewerTarget,
  useEvidenceViewer,
} from "./EvidenceViewer";

function Inner({ target }: { target: EvidenceViewerTarget }): JSX.Element {
  const viewer = useEvidenceViewer(target);
  return <EvidenceViewerBody host="dock" target={target} viewer={viewer} />;
}

/** The dock's Viewer tab body: what `dockHost(..., { viewer })` mounts (A-01's DockHost). */
export function ViewerPane({ target }: { target: EvidenceViewerTarget }): JSX.Element {
  const key = [target.versionId, target.matchId ?? "", target.anchor?.id ?? ""].join("|");
  return (
    <div data-screen="SHL-08" data-host="dock" className="flex min-h-0 flex-1 flex-col">
      <MatchScope key={key}>
        <Inner target={target} />
      </MatchScope>
    </div>
  );
}
