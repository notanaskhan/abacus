// A-07-T50 (TASK-6820): the A-07 journey steps' shared helpers. Fixture builds open each artboard in
// the /components gallery on its own scenario (persona and demo clock from the scenario); the
// full-stack and staging walks wait for the S36 batch's deploy with `audits.letters`,
// `audits.report_release` and `audits.archive` on for PF-X1 (DEC-1530), so they are `test.fixme` there.
import type { Page } from "@playwright/test";
import { expect } from "../harness";

export const A07_LIVE =
  "A-07 · A-07-T50 staging walk after the S36 batch deploy with audits.letters, audits.report_release and audits.archive on for PF-X1 · S36, Fri Mar 17, 2028";
export const A08_AUD26 =
  "A-08 · AUD-26 review and compilation reports (SSARS) · issue: A-07-T50 j05 6 waits on AUD-26";

/** A screen's artboard in the firm's gallery (fixture builds only). */
export function a07(id: string, state: string): string {
  return `/components/screens/${id}?st=${state}`;
}

export function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

/** The screen's root (the gallery opened it on the state the URL names). */
export async function onScreen(page: Page, id: string): Promise<void> {
  await expect(page.locator(`[data-screen='${id}']`).first()).toBeVisible();
}

/** INV-1 on a person's screen: no agent-owned control carries a decision verb. */
export async function noAgentDecision(page: Page): Promise<void> {
  const agentControls = page.locator("[data-agent] button, [data-agent-owned] button");
  for (const verb of ["Approve", "Sign off", "Release", "Send", "Post", "Decide", "Concur", "Lock"]) {
    await expect(agentControls.filter({ hasText: verb })).toHaveCount(0);
  }
}
