// T-06-T23 (DEC-5636; SPEC-702): each of the 44 T-06 artboards opens from `?screen=<ID>&st=<state>`
// in fixture mode, at its contract persona and demo clock, with no network call.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { SCREEN_SCENARIOS, screenScenario } from "../screen-scenarios";

const IDS = ["TXP-03", "TXP-04", "TXP-08", "TXP-09", "TXP-13", "TAX-11", "CLI-03", "AUD-38"];
const { process } = globalThis as unknown as { process: { cwd: () => string } };
const DOCS = join(process.cwd(), "..", "..", "docs", "screens");

function artboards(id: string): string[] {
  const text = readFileSync(join(DOCS, `${id}.md`), "utf8");
  return [...text.matchAll(/^\| ([a-z][a-z0-9′]*) \| .*? \| `[^`]+` \|/gm)].map((m) =>
    (m[1] ?? "").replace("′", "p"),
  );
}

describe("T-06 fixture mode", () => {
  it.each(IDS)("%s has a scenario for every contract artboard", (id) => {
    expect(Object.keys(SCREEN_SCENARIOS[id]?.scenarios ?? {}).sort()).toEqual(
      artboards(id).sort(),
    );
  });

  it("44 artboards in all", () => {
    expect(IDS.reduce((n, id) => n + artboards(id).length, 0)).toBe(44);
  });

  it("every artboard opens from its URL with a persona and a parseable clock", () => {
    for (const id of IDS) {
      for (const st of artboards(id)) {
        const choice = screenScenario(`?screen=${id}&st=${st}`);
        expect(choice, `${id} ${st}`).not.toBeNull();
        expect(choice?.scenario.persona).toMatch(/^[a-z]+-[a-z]+$/);
        expect(Number.isNaN(Date.parse(choice?.scenario.clock ?? ""))).toBe(false);
      }
    }
  });
});
