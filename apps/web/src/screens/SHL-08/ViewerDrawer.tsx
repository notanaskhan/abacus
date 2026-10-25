// SHL-08 on its first host, the O2 drawer (P-03-T14; AC3.1): 480 wide, no scrim (the record stays
// live beside it), the file name centred in the header with "Processing…" while the version is
// still being made, "Open in Files" on the right and Download only in the ⋯ menu. Opened through
// `?ov=viewer:…` (routes/firm/viewer.tsx): Back closes it; Escape and ✕ close it with `replace`.

import { Button, Drawer, MatchScope, Pill, registryWord } from "@abacus/ui";
import type { JSX } from "react";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { COPY } from "./copy";
import {
  EvidenceViewerBody,
  type EvidenceViewerTarget,
  useEvidenceViewer,
} from "./EvidenceViewer";

export interface ViewerDrawerProps {
  target: EvidenceViewerTarget;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Hold the drawer open in place (the gallery's artboards). */
  forceState?: "open";
}

function Inner({ target, open, onOpenChange, forceState }: ViewerDrawerProps): JSX.Element {
  const viewer = useEvidenceViewer(target);
  const processing = viewer.data.manifest?.status === "processing";
  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={viewer.data.file.name}
      width={480}
      peek
      bare
      more={viewer.menu}
      meta={
        <>
          {processing && (
            <Pill variant="muted" size="sm">
              {registryWord("viewer", "processing").label}
            </Pill>
          )}
          {PLANNED_VISIBLE && (
            <Button size="sm" variant="secondary" disabled title={COPY.openInFilesHint}>
              {COPY.menu.openInFiles}
            </Button>
          )}
        </>
      }
      {...(forceState === undefined ? {} : { forceState })}
    >
      <div data-screen="SHL-08" data-host="drawer" className="flex min-h-0 flex-1 flex-col">
        <EvidenceViewerBody host="drawer" target={target} viewer={viewer} />
      </div>
    </Drawer>
  );
}

/** The source viewer drawer: one match store for its card and its pages. */
export function ViewerDrawer(props: ViewerDrawerProps): JSX.Element {
  return (
    <MatchScope>
      <Inner {...props} />
    </MatchScope>
  );
}
