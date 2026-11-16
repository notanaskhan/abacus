import type { OverlayRef } from "../../app-core/overlays";
import { ov } from "../../routes/to";

// ADM-08's designed link (link-contract rule 1; S47, TASK-8338): the host route passes it to the
// screen's callback.

/** The integration's name on the mappings page: WB-11, its detail drawer. */
export function integrationOverlay(key: string): OverlayRef {
  return ov.WB11(key);
}
