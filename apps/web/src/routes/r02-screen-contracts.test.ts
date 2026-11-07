// R-02-T01 (SPEC-646; TASK-5101): every R-02 screen contract marks each artboard letter live,
// fixture-only or deferred, records its deviations and names every outbound handoff link.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const { process } = globalThis as unknown as { process: { cwd: () => string } };
const WEB = process.cwd();
const REPO = join(WEB, "..", "..");
const GRAPH = JSON.parse(
  readFileSync(join(WEB, "src", "routes", "handoff-links.json"), "utf8"),
) as { links: { from: string; to: string }[] };

const ARTBOARDS: Record<string, string[]> = {
  "POR-08": ["a", "a2", "b", "c", "d", "e", "e2", "f"],
  "POR-09": ["a", "a2", "b", "c", "d", "e", "f", "g", "h", "i"],
  "POR-15": ["a", "b", "c", "d", "e", "f"],
};
const DEVIATIONS = ["DV-01", "DV-02", "DV-03", "DV-04", "DV-05", "DV-06", "DV-07", "DV-08", "DV-09", "DV-10", "DV-11", "DV-12"];

function section(doc: string, heading: string): string[] {
  const start = doc.indexOf(`## ${heading}`);
  const rest = doc.slice(start + heading.length + 3);
  const end = rest.indexOf("\n## ");
  return (end === -1 ? rest : rest.slice(0, end)).split("\n");
}

const docs = Object.fromEntries(
  Object.keys(ARTBOARDS).map((id) => [id, readFileSync(join(REPO, "docs", "screens", `${id}.md`), "utf8")]),
);

describe("R-02 screen contracts", () => {
  it("covers DV-01 to DV-12 across the three contracts", () => {
    const all = Object.values(docs).join("\n");
    for (const dv of DEVIATIONS) expect(all, dv).toContain(`- ${dv}:`);
  });

  for (const [id, letters] of Object.entries(ARTBOARDS)) {
    const doc = docs[id] ?? "";

    it(`${id} marks every artboard live, fixture-only or deferred`, () => {
      const rows = section(doc, "States").filter((l) => l.startsWith("| "));
      for (const letter of letters) {
        const row = rows.find((r) => r.startsWith(`| ${letter} |`));
        expect(row, `${id} ${letter}`).toBeDefined();
        expect(row).toMatch(/\| (live|fixture-only|deferred)[^|]*\|$/);
      }
    });

    it(`${id} names every outbound target of the handoff link graph`, () => {
      const links = section(doc, "Links").join("\n");
      const targets = new Set(GRAPH.links.filter((l) => l.from === id).map((l) => l.to));
      for (const target of targets) expect(links, `${id} → ${target}`).toContain(`| ${target} |`);
    });
  }
});
