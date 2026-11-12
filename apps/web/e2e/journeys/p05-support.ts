// P-05-T15 (TASK-7311; P-05 §10 item 1): the collaboration journeys' shared helpers. Fixture builds
// open SHL-17, SHL-18 and AUD-29 on their gallery artboards (persona and demo clock from each
// scenario); the staging walk with real auth waits for the canary flip of `collaboration.v2` and
// `audit_trail.engagement_activity` (P-05-T16, Tue Mar 28, 2028), so it is `test.fixme` there.
import type { Page } from "@playwright/test";
import { expect } from "../harness";

export const P05_LIVE =
  "P-05 · P-05-T16 canary flip of collaboration.v2 and audit_trail.engagement_activity (Tue Mar 28, 2028); staging walk after it";

/** A collaboration artboard in the firm's gallery, as a persona. */
export function p05(id: "SHL-17" | "SHL-18" | "AUD-29", state: string, persona?: string): string {
  const as = persona === undefined ? "" : `&as=${persona}`;
  return `/components/screens/${id}?st=${state}${as}`;
}

/** INV-1: nothing the agent owns offers a decision, and the collaboration surfaces never block
 * sign-off (comments and to-dos are internal). */
export async function nothingBlocks(page: Page): Promise<void> {
  for (const verb of ["Approve", "Sign off", "Release", "Send", "Decide"]) {
    await expect(
      page.locator("[data-agent] button, [data-agent-owned] button").filter({ hasText: verb }),
    ).toHaveCount(0);
  }
}
