// C-01-T51 (TASK-8701): open a portal screen registered in the /components gallery at one artboard,
// as r02-support's `artboardAs` does for POR-08, POR-09 and POR-15.
import { type Journey, expect } from "../harness";
import type { PersonaSlug } from "../harness/personas";

export async function artboardAt(
  journey: Journey,
  who: PersonaSlug,
  screen: "POR-11",
  st: string,
  width: 1400 | 390 = 1400,
): Promise<void> {
  await journey.page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
  await journey.as(
    who,
    `/components/screens/${screen}?st=${st}&frame=1${width === 390 ? "&w=390" : ""}`,
  );
  await expect(journey.page.locator(`[data-artboard='${st}']`)).toBeVisible();
}
