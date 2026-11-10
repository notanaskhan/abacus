// R-02-T23 (R-02 §5.6): the R-02 portal steps walk POR-08, POR-09 and POR-15 on their artboards in
// the fixture project (the screens' fixture scenarios, each with its persona and clock), at 1400
// and 390; `journey.step` runs axe and INV-1 to INV-5 after each. The full stack and staging walk
// them once the providers register (A-07, A-08, C-02) and the batch deploys.
import type { Page } from "@playwright/test";
import { type Journey, expect } from "../harness";
import type { PersonaSlug } from "../harness/personas";

export type Width = 1400 | 390;
export const WIDTHS: readonly Width[] = [1400, 390];

/** Open `screen` at artboard `st` as `who`, at `width`. */
export async function artboardAs(
  journey: Journey,
  who: PersonaSlug,
  screen: "POR-08" | "POR-09" | "POR-15",
  st: string,
  width: Width = 1400,
): Promise<void> {
  await journey.page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
  await journey.as(
    who,
    `/components/screens/${screen}?st=${st}&frame=1${width === 390 ? "&w=390" : ""}`,
  );
  await expect(journey.page.locator(`[data-artboard='${st}']`)).toBeVisible();
}

/** The artboard's own region, so a step reads only what that artboard draws. */
export function board(page: Page, st: string) {
  return page.locator(`[data-artboard='${st}']`);
}

/** The white-label rule (INV-4, DEC-01): no portal step shows the product's name. */
export async function noProductName(page: Page, st: string): Promise<void> {
  await expect(board(page, st)).not.toContainText("Accrued");
}

export function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}
