// R-02-T23 (R-02 §5.6): POR-08's screen spec. Every built artboard as its scenario's persona, at 1400
// and 390, through the journey harness, so each one runs axe (serious and critical block) and the
// five invariants (INV-1 to INV-5); the portal never shows the product's name (INV-4, DEC-01).
import { test } from "../harness";
import type { PersonaSlug } from "../harness/personas";
import { WIDTHS, artboardAs, noProductName } from "../journeys/r02-support";

const STATES = ["a", "a2", "b", "c", "d", "e", "e2", "f"] as const;
const PERSONA: Record<(typeof STATES)[number], PersonaSlug> = {
  a: "ben-ashby",
  a2: "ben-ashby",
  b: "tess-moreno",
  c: "ben-ashby",
  d: "ben-ashby",
  e: "dana-kowalski",
  e2: "dana-kowalski",
  f: "ben-ashby",
};

test.describe("POR-08", () => {
  test.beforeEach(({ journey }) => {
    test.skip(journey.project !== "fixture", "artboards are the fixture project's");
  });

  for (const st of STATES) {
    for (const width of WIDTHS) {
      test(`POR-08${st} at ${String(width)}: axe and INV-1 to INV-5`, async ({ journey }) => {
        await artboardAs(journey, PERSONA[st], "POR-08", st, width);
        await journey.step(`POR-08${st} at ${String(width)}`, async (page) => {
          await noProductName(page, st);
        });
      });
    }
  }
});
