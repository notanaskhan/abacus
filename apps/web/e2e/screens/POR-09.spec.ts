// R-02-T23 (R-02 §5.6): POR-09's screen spec. Every built artboard as its scenario's persona, at 1400
// and 390, through the journey harness, so each one runs axe (serious and critical block) and the
// five invariants (INV-1 to INV-5); the portal never shows the product's name (INV-4, DEC-01).
import { test } from "../harness";
import type { PersonaSlug } from "../harness/personas";
import { WIDTHS, artboardAs, noProductName } from "../journeys/r02-support";

const STATES = ["a", "a2", "b", "c", "d", "e", "f"] as const;
const PERSONA: Record<(typeof STATES)[number], PersonaSlug> = {
  a: "dana-kowalski",
  a2: "dana-kowalski",
  b: "dana-kowalski",
  c: "dana-kowalski",
  d: "meera-shah",
  e: "tess-moreno",
  f: "luis-ferrante",
};

test.describe("POR-09", () => {
  test.beforeEach(({ journey }) => {
    test.skip(journey.project !== "fixture", "artboards are the fixture project's");
  });

  for (const st of STATES) {
    for (const width of WIDTHS) {
      test(`POR-09${st} at ${String(width)}: axe and INV-1 to INV-5`, async ({ journey }) => {
        await artboardAs(journey, PERSONA[st], "POR-09", st, width);
        await journey.step(`POR-09${st} at ${String(width)}`, async (page) => {
          await noProductName(page, st);
        });
      });
    }
  }
});
