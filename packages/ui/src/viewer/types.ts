// The E5 SourceViewer's own shapes (F-05-T47; C-08 Doc Kit `doc-viewer-types.ts`, bound to C4 §3.3
// and §3.4). L2 rule: the kit never imports the API client; a screen maps C4's
// `ViewerManifestOut`, `ViewerRegionsOut` and `PiiMaskOut` onto these (the consumer contract in
// apps/web/src/fixtures/contracts/design-system.contract.test.ts pins the mapping).
import type { MatchId } from "../tracing/types";

/** `[x0, top, x1, bottom]` in PDF points, top-left origin, unrotated page space (C4 §3.3). */
export type PtRect = readonly [number, number, number, number];

export interface ViewerPage {
  n: number;
  width_pt: number;
  height_pt: number;
  rotation: 0 | 90 | 180 | 270;
  /** The server-rendered, masked page image: a same-origin URL (or, in fixtures, a PNG data URL).
   * Never the client's file, never a document to parse. */
  src: string;
}

export interface LinkedFigure {
  /** "Form 1040 · Line 3b" */
  label: string;
  /** "$4,812", formatted by the server or format.ts. */
  value: string;
}

export interface ViewerRegion {
  /** The server's `match_id` (C4 `ViewerRegionOut`), never derived from text (INV-2). */
  match: MatchId;
  page: number;
  rects: readonly PtRect[];
  /** Findable words (C4 `label`, client text: rendered and searched as text only). */
  label?: string | null;
  linkedFigure?: LinkedFigure;
  /** A statement row: lit as a band with the ring on its top and bottom edges only. */
  band?: boolean;
  /** A record the viewer can see cites this region (C4 `citation_id`): auto-highlight outlines it
   * (SHL-08h). */
  cited?: boolean;
}

export interface ViewerMask {
  id: string;
  page: number;
  rect: PtRect;
  /** `ssn`, `itin`, `ein`, `bank_account`, `routing_number`, `dob`. */
  kind: string;
  /** The mask token: `•••-••-6081`. */
  display: string;
}

export type ViewerStatus =
  "processing" | "ready" | "password_protected" | "unreadable" | "not_previewable";

export interface ViewerFile {
  name: string;
  pages: readonly ViewerPage[];
  regions: readonly ViewerRegion[];
  masks?: readonly ViewerMask[];
}

/** A value revealed by the logged endpoint (P-03), shown in place of its mask until it expires. */
export interface RevealedValue {
  value: string;
  /** "Revealed by Samuel Ito · 9:31 AM · logged to the audit trail" */
  note: string;
}
