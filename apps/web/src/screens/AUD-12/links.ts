import type { OverlayRef } from "../../app-core/overlays";
import { ov } from "../../routes/to";

// AUD-12's designed links (link-contract rule 1; S47 end pass, TASK-8337): the host route passes
// these to the screen's callbacks.

/** "Raise exception…": SHL-15, a new issue on the test (the exception routes to AUD-15). */
export function exceptionOverlay(testId: string, engagementId: string): OverlayRef {
  return ov.SHL15New("je_test", testId, engagementId);
}

/** A raised exception's issue: SHL-15 with its fix instructions. */
export function issueOverlay(issueId: string): OverlayRef {
  return ov.SHL15(issueId);
}

/** "Sampling": AUD-11 over the testing workspace, on the test's work item. */
export function samplingOverlay(workItemId: string): OverlayRef {
  return ov.AUD11(workItemId);
}
