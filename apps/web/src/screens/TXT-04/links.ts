import type { OverlayRef } from "../../app-core/overlays";
import { ov, to } from "../../routes/to";

// TXT-04's designed links (link-contract rule 1; S47 end pass, TASK-8337): the host route passes
// these to the screen's callbacks.

/** Checkpoints on the estate workpapers: SHL-16 over the return. */
export function checkpointsOverlay(returnId: string): OverlayRef {
  return ov.SHL16("tax_return", returnId);
}

/** "Export to CCH Axcess": TAX-09, the return's engine sync. */
export function engineSyncOverlay(returnId: string): OverlayRef {
  return ov.TAX09(returnId);
}

/** The due chip's "4768": TAX-13, extensions. */
export function extensionsLink(): ReturnType<typeof to.TAX13> {
  return to.TAX13();
}

/** "Request from Paul Thornbury": SHL-14, a new request on the return's binder. */
export function requestOverlay(binderId: string): OverlayRef {
  return ov.SHL14("new", binderId);
}

/** A figure's provenance: SHL-09 on its field. */
export function provenanceOverlay(returnId: string, fieldKey: string): OverlayRef {
  return ov.SHL09("tax_return", returnId, fieldKey);
}

/** "2023 Form 709 as filed": FIL-01, the files library. */
export function filesLink(): ReturnType<typeof to.FIL01> {
  return to.FIL01();
}

/** The intake link: TAX-03, the return's intake. */
export function intakeLink(returnId: string): ReturnType<typeof to.TAX03> {
  return to.TAX03({ returnId });
}
