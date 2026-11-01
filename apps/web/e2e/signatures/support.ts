// The signature specs' shared pieces (N-02-T40): the owner annotation for a step the hosted
// projects cannot walk yet, the hosted-URL skip, and the /components gallery path a fixture step
// opens for a screen with no route of its own (SIG-01, SIG-02 as an artboard).
import type { Page } from "@playwright/test";
import { type HarnessProject, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};

export function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

/** The M13 walk on staging and the canary (N-02 §10.1): until then the hosted runs skip. */
export const M13 = "N-02 · N-02-T42 journey E2E for M13 on staging · S21, Fri Aug 20, 2027";

export function skipUnhosted(project: HarnessProject): void {
  const hosted = project === "staging" || project === "canary";
  test.skip(
    hosted && HOSTED_URL[project] === undefined,
    `ABACUS_${project.toUpperCase()}_URL is not set`,
  );
}

/** A screen's artboard in the /components gallery, framed (fixture builds only). */
export function artboard(screen: string, state: string): string {
  return `/components/screens/${screen}?st=${state}&frame=1`;
}

/** N-02-T42: POR-06's states open on the Sign list; a person opens the envelope from it. */
export async function openEnvelope(page: Page, name: RegExp): Promise<void> {
  await page.getByRole("button", { name }).first().click();
  await page.waitForURL(/\/sign\/[^/?]+/);
}
